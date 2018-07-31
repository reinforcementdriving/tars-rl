import os
import tensorflow as tf
import time
from .server_replay_buffer import ServerBuffer
from threading import Lock, Thread
import multiprocessing


def make_session(num_cpu=None, make_default=False, graph=None):
    """Returns a session that will use <num_cpu> CPU's only"""
    if num_cpu is None:
        num_cpu = int(os.getenv('RCALL_NUM_CPU', multiprocessing.cpu_count()))
    tf_config = tf.ConfigProto(
        inter_op_parallelism_threads=num_cpu,
        intra_op_parallelism_threads=num_cpu)
    tf_config.gpu_options.allow_growth = True
    if make_default:
        return tf.InteractiveSession(config=tf_config, graph=graph)
    else:
        return tf.Session(config=tf_config, graph=graph)


def single_threaded_session():
    """Returns a session which will only use a single CPU"""
    return make_session(num_cpu=1)


class RLTrainer:
    def __init__(
            self,
            observation_shapes,
            action_size,
            gpu_id=0,
            batch_size=96,
            experience_replay_buffer_size=1000000,
            use_prioritized_buffer=False,
            use_synchronous_update=True,
            n_step=1,
            train_every_nth=4,
            history_length=3,
            initial_beta=0.4,
            target_critic_update_period=500,
            target_actor_update_period=500,
            start_learning_after=5000,
            show_stats_period=2000,
            save_model_period=10000,
            save_path='ckpt/'):

        self._observation_shapes = observation_shapes
        self._action_size = action_size
        self._batch_size = batch_size
        self._buffer_size = experience_replay_buffer_size
        self._start_learning_after = start_learning_after
        self._n_step = n_step
        self._train_every = train_every_nth
        self._target_critic_update_period = target_critic_update_period
        self._target_actor_update_period = target_actor_update_period
        self._show_stats_period = show_stats_period
        self._save_model_period = save_model_period
        self._hist_len = history_length
        self._beta = initial_beta
        self._use_prioritized_buffer = use_prioritized_buffer
        self._use_synchronous_update = use_synchronous_update
        self._save_path = save_path
        self._gpu_id = gpu_id

        self.server_buffer = ServerBuffer(
            self._buffer_size, observation_shapes, action_size)
        self._train_loop_step_lock = Lock()
        self._step_index = 0

    def set_algorithm(self, algo):
        self._algo = algo

    def init(self):
        pass

    def store_episode(self, episode):
        self.server_buffer.push_episode(episode)

    # for asynchronous acts and trains
    def start_training(self):
        if not self._use_synchronous_update:
            def train_loop():
                while True:
                    buffer_size = self.server_buffer.get_stored_in_buffer()
                    if buffer_size > self._start_learning_after:
                        if buffer_size > self._step_index * self._train_every:
                            self.train_step()
                            self._step_index += 1
                    elif buffer_size < self._start_learning_after \
                            and self._step_index % 10 == 0:
                        print('--- buffer size {}'.format(buffer_size))
                        time.sleep(1.0)

            th = Thread(target=train_loop)
            th.start()
        else:
            pass

    # for synchronous acts and trains
    def train_loop_step(self):

        with self._train_loop_step_lock:

            buffer_size = self.server_buffer.get_stored_in_buffer()
            if buffer_size > self._start_learning_after:
                if buffer_size > self._step_index * self._train_every:
                    i = 0
                    while i * self._train_every < 1:
                        self.train_step()
                        self._step_index += 1
                        i += 1
            elif buffer_size < self._start_learning_after:
                print('--- buffer size {}'.format(buffer_size))

    def act_batch(self, states, mode='default'):
        if mode == 'default':
            actions = self._algo.act_batch(states)
        elif mode == 'sac_deterministic':
            actions = self._algo.act_batch_deterministic(states)
        elif mode == 'with_gradients':
            # actually, here it will return actions and grads
            actions = self._algo.act_batch_with_gradients(states)
        else:
            raise NotImplementedError
        if self._use_synchronous_update:
            self.train_loop_step()
        return actions

    def train_step(self):

        queue_size = self.server_buffer.get_stored_in_buffer()

        if self._use_prioritized_buffer:

            prio_batch = self.server_buffer.get_prioritized_batch(
                self._batch_size,
                history_len=self._hist_len,
                n_step=self._n_step,
                beta=self._beta)
            batch, indices, is_weights = prio_batch
            loss = self._algo.train(batch, is_weights)
            td_errors = self._algo.get_td_errors(batch).ravel()
            self.server_buffer.update_td_errors(indices, td_errors)
            self._beta = min(1.0, self._beta + 1e-6)
        else:
            batch = self.server_buffer.get_batch(self._batch_size,
                                                 history_len=self._hist_len,
                                                 n_step=self._n_step)
            loss = self._algo.train(batch)

        if self._step_index % self._target_critic_update_period == 0:
            self._algo.target_critic_update()

        if self._step_index % self._target_actor_update_period == 0:
            self._algo.target_actor_update()

        if self._step_index % self._show_stats_period == 0:
            print(
                'trains: {} loss: {} stored: {}'.format(
                    self._step_index, loss, queue_size))

        self.save()

    def save(self):
        pass


class TFRLTrainer(RLTrainer):
    def init(self):
        self._sess = make_session(num_cpu=1, make_default=True)
        self._logger = tf.summary.FileWriter("logs")

        self._logger.add_graph(self._sess.graph)
        self._sess.run(tf.global_variables_initializer())
        self._saver = tf.train.Saver(max_to_keep=None)
        self._algo.target_network_init(self._sess)

    def act_batch(self, states, mode='default'):
        if mode == 'default':
            actions = self._algo.act_batch(self._sess, states)
        if mode == 'sac_deterministic':
            actions = self._algo.act_batch_deterministic(self._sess, states)
        if mode == 'with_gradients':
            # actually, here it will return actions and grads
            actions = self._algo.act_batch_with_gradients(self._sess, states)
        if self._use_synchronous_update:
            self.train_loop_step()
        return actions

    def train_step(self):

        queue_size = self.server_buffer.get_stored_in_buffer()

        if self._use_prioritized_buffer:

            prio_batch = self.server_buffer.get_prioritized_batch(
                self._batch_size,
                history_len=self._hist_len,
                n_step=self._n_step,
                beta=self._beta)
            batch, indices, is_weights = prio_batch
            loss = self._algo.train(self._sess, batch, is_weights)
            td_errors = self._algo.get_td_errors(self._sess, batch).ravel()
            self.server_buffer.update_td_errors(indices, td_errors)
            self._beta = min(1.0, self._beta + 1e-6)
        else:
            batch = self.server_buffer.get_batch(self._batch_size,
                                                 history_len=self._hist_len,
                                                 n_step=self._n_step)
            loss = self._algo.train(self._sess, batch)

        if self._step_index % self._target_critic_update_period == 0:
            self._algo.target_critic_update(self._sess)

        if self._step_index % self._target_actor_update_period == 0:
            self._algo.target_actor_update(self._sess)

        if self._step_index % self._show_stats_period == 0:
            print(
                'trains: {} loss: {} stored: {}'.format(
                    self._step_index, loss, queue_size))

        self.save()

    def save(self):
        if self._step_index % self._save_model_period == 0:
            save_path = self._saver.save(
                self._sess, self._save_path + 'model-{}.ckpt'.format(
                    self._step_index))
            print("Model saved in file: %s" % save_path)
