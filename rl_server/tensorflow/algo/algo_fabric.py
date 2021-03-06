import copy

import tensorflow as tf

from rl_server.tensorflow.algo.ddpg import DDPG
from rl_server.tensorflow.algo.categorical_ddpg import CategoricalDDPG
from rl_server.tensorflow.algo.quantile_ddpg import QuantileDDPG
from rl_server.tensorflow.algo.td3 import TD3
from rl_server.tensorflow.algo.quantile_td3 import QuantileTD3
from rl_server.tensorflow.algo.sac import SAC
from rl_server.tensorflow.algo.base_algo import create_placeholders
from rl_server.tensorflow.algo.prioritized_ddpg import PrioritizedDDPG
from rl_server.tensorflow.networks.actor_networks_lstm import ActorNetwork as ActorNetworkLSTM
from rl_server.tensorflow.networks.critic_networks_lstm import CriticNetwork as CriticNetworkLSTM
from rl_server.tensorflow.networks.actor_networks import (
    ActorNetwork as ActorNetworkFF,
    GaussActorNetwork as GaussActorNetworkFF
)
from rl_server.tensorflow.networks.critic_networks import CriticNetwork as CriticNetworkFF


def create_algorithm(
    algo_config,
    placeholders=None,
    scope_postfix=0
):
    # networks
    if algo_config.actor.lstm_network:
        ActorNetwork = ActorNetworkLSTM
        GaussActorNetwork = None
    else:
        ActorNetwork = ActorNetworkFF
        GaussActorNetwork = GaussActorNetworkFF

    if algo_config.critic.lstm_network:
        CriticNetwork = CriticNetworkLSTM
    else:
        CriticNetwork = CriticNetworkFF

    actor_params = copy.deepcopy(algo_config.as_obj()["actor"])
    del actor_params['lstm_network']
    critic_params = copy.deepcopy(algo_config.as_obj()["critic"])
    del critic_params['lstm_network']

    # algorithm
    name = algo_config.algo_name
    print('--- creating {}'.format(name))
    
    scope_postfix = str(scope_postfix)
    actor_scope = "actor_" + scope_postfix
    critic_scope = "critic_" + scope_postfix
    algo_scope = "algorithm_" + scope_postfix

    _, state_shapes, action_size = algo_config.get_env_shapes()
    if placeholders is None:
        placeholders = create_placeholders(state_shapes, action_size)
    
    actor_lr = placeholders[0]
    critic_lr = placeholders[1]

    if name != "sac" and name != "td3" and name != "quantile_td3":

        actor = ActorNetwork(
            state_shape=state_shapes[0],
            action_size=action_size,
            **actor_params,
            scope=actor_scope)

        if name == "ddpg":
            critic = CriticNetwork(
                state_shape=state_shapes[0],
                action_size=action_size,
                **critic_params,
                scope=critic_scope)

            if algo_config.server.use_prioritized_buffer:
                DDPG_algorithm = PrioritizedDDPG
            else:
                DDPG_algorithm = DDPG
        elif name == "categorical_ddpg":
            assert not algo_config.server.use_prioritized_buffer, '{} have no prioritized version. use ddpg'.format(
                name)
            critic = CriticNetwork(
                state_shape=state_shapes[0],
                action_size=action_size,
                **critic_params,
                scope=critic_scope)
            DDPG_algorithm = CategoricalDDPG
        elif name == "quantile_ddpg":
            assert not algo_config.server.use_prioritized_buffer, '{} have no prioritized version. use ddpg'.format(
                name)
            critic = CriticNetwork(
                state_shape=state_shapes[0],
                action_size=action_size,
                **critic_params,
                scope=critic_scope)
            DDPG_algorithm = QuantileDDPG
        else:
            raise NotImplementedError

        agent_algorithm = DDPG_algorithm(
            state_shapes=state_shapes,
            action_size=action_size,
            actor=actor,
            critic=critic,
            actor_optimizer=tf.train.AdamOptimizer(
                learning_rate=actor_lr),
            critic_optimizer=tf.train.AdamOptimizer(
                learning_rate=critic_lr),
            **algo_config.as_obj()["algorithm"],
            scope=algo_scope,
            placeholders=placeholders,
            actor_optim_schedule=algo_config.as_obj()["actor_optim"],
            critic_optim_schedule=algo_config.as_obj()["critic_optim"],
            training_schedule=algo_config.as_obj()["training"])

    elif name == "sac":

        assert not algo_config.server.use_prioritized_buffer, '{} have no prioritized version. use ddpg'.format(name)
        assert not algo_config.actor.lstm_network, '{} actor network don\'t support LSTM'.format(name)

        actor = GaussActorNetwork(
            state_shape=state_shapes[0],
            action_size=action_size,
            **actor_params,
            scope=actor_scope)

        critic_v_params = copy.deepcopy(critic_params)
        critic_v_params['action_insert_block'] = -1
        critic_v = CriticNetwork(
            state_shape=state_shapes[0],
            action_size=action_size,
            **critic_v_params,
            scope="critic_v_" + scope_postfix)
        critic_q1 = CriticNetwork(
            state_shape=state_shapes[0],
            action_size=action_size,
            **critic_params,
            scope="critic_q1_" + scope_postfix)
        critic_q2 = CriticNetwork(
            state_shape=state_shapes[0],
            action_size=action_size,
            **critic_params,
            scope="critic_q2_" + scope_postfix)

        agent_algorithm = SAC(
            state_shapes=state_shapes,
            action_size=action_size,
            actor=actor,
            critic_v=critic_v,
            critic_q1=critic_q1,
            critic_q2=critic_q2,
            actor_optimizer=tf.train.AdamOptimizer(
                learning_rate=actor_lr),
            critic_v_optimizer=tf.train.AdamOptimizer(
                learning_rate=critic_lr),
            critic_q1_optimizer=tf.train.AdamOptimizer(
                learning_rate=critic_lr),
            critic_q2_optimizer=tf.train.AdamOptimizer(
                learning_rate=critic_lr),
            **algo_config.as_obj()["algorithm"],
            scope=algo_scope,
            placeholders=placeholders,
            actor_optim_schedule=algo_config.as_obj()["actor_optim"],
            critic_optim_schedule=algo_config.as_obj()["critic_optim"],
            training_schedule=algo_config.as_obj()["training"])

    elif name == "td3":

        assert not algo_config.server.use_prioritized_buffer, '{} have no prioritized version. use ddpg'.format(name)

        actor = ActorNetwork(
            state_shape=state_shapes[0],
            action_size=action_size,
            **actor_params,
            scope=actor_scope)
       
        critic1 = CriticNetwork(
            state_shape=state_shapes[0],
            action_size=action_size,
            **critic_params,
            scope="critic1_" + scope_postfix)
        critic2 = CriticNetwork(
            state_shape=state_shapes[0],
            action_size=action_size,
            **critic_params,
            scope="critic2_" + scope_postfix)

        agent_algorithm = TD3(
            state_shapes=state_shapes,
            action_size=action_size,
            actor=actor,
            critic1=critic1,
            critic2=critic2,
            actor_optimizer=tf.train.AdamOptimizer(
                learning_rate=actor_lr),
            critic1_optimizer=tf.train.AdamOptimizer(
                learning_rate=critic_lr),
            critic2_optimizer=tf.train.AdamOptimizer(
                learning_rate=critic_lr),
            **algo_config.as_obj()["algorithm"],
            scope=algo_scope,
            placeholders=placeholders,
            actor_optim_schedule=algo_config.as_obj()["actor_optim"],
            critic_optim_schedule=algo_config.as_obj()["critic_optim"],
            training_schedule=algo_config.as_obj()["training"])
        
    elif name == "quantile_td3":

        assert not algo_config.server.use_prioritized_buffer, '{} have no prioritized version. use ddpg'.format(name)

        actor = ActorNetwork(
            state_shape=state_shapes[0],
            action_size=action_size,
            **actor_params,
            scope=actor_scope)
       
        critic1 = CriticNetwork(
            state_shape=state_shapes[0],
            action_size=action_size,
            **critic_params,
            scope="critic1_" + scope_postfix)
        critic2 = CriticNetwork(
            state_shape=state_shapes[0],
            action_size=action_size,
            **critic_params,
            scope="critic2_" + scope_postfix)

        agent_algorithm = QuantileTD3(
            state_shapes=state_shapes,
            action_size=action_size,
            actor=actor,
            critic1=critic1,
            critic2=critic2,
            actor_optimizer=tf.train.AdamOptimizer(
                learning_rate=actor_lr),
            critic1_optimizer=tf.train.AdamOptimizer(
                learning_rate=critic_lr),
            critic2_optimizer=tf.train.AdamOptimizer(
                learning_rate=critic_lr),
            **algo_config.as_obj()["algorithm"],
            scope=algo_scope,
            placeholders=placeholders,
            actor_optim_schedule=algo_config.as_obj()["actor_optim"],
            critic_optim_schedule=algo_config.as_obj()["critic_optim"],
            training_schedule=algo_config.as_obj()["training"])
    
    return agent_algorithm
