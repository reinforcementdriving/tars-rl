import time
from datetime import datetime

from tensorboardX import SummaryWriter

from misc.defaults import create_if_need


class RLLogger:
    def __init__(
        self,
        logdir,
        agent_id,
        validation,
        env
    ):
        self._logdir = logdir
        self._agent_id = agent_id
        self._env = env
        path_to_rewards_train = f"{self._logdir}/rewards-train-{self._agent_id}.txt"
        path_to_rewards_test = f"{self._logdir}/rewards-test-{self._agent_id}.txt"

        current_date = datetime.now().strftime('%y-%m-%d-%H-%M-%S-%M-%f')
        if validation:
            self._path_to_rewards = path_to_rewards_test
            logpath = f"{self._logdir}/agent-valid-{self._agent_id}-{current_date}"
        else:
            self._path_to_rewards = path_to_rewards_train
            logpath = f"{self._logdir}/agent-train-{self._agent_id}-{current_date}"
        create_if_need(logpath)
        self._logger = SummaryWriter(logpath)
        self._start_time = time.time()
        
    def log(self, episode_index, n_steps):
        elapsed_time = time.time() - self._start_time
        print("--- episode ended {} {} {} {} {}".format(
            self._agent_id, episode_index, self._env.time_step,
            self._env.get_total_reward(), self._env.get_total_reward_shaped()))

        self._logger.add_scalar("steps", n_steps, episode_index)
        self._logger.add_scalar(
            "reward", self._env.get_total_reward(), episode_index)
        self._logger.add_scalar(
            "episode per minute",
            episode_index / elapsed_time * 60,
            episode_index)
        self._logger.add_scalar(
            "steps per second",
            n_steps / elapsed_time,
            episode_index)

        with open(self._path_to_rewards, "a") as f:
            f.write(
                str(self._agent_id) + " " +
                str(episode_index) + " " +
                str(self._env.get_total_reward()) + "\n")
                
        self._start_time = time.time()
