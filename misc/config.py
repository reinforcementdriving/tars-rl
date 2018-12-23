import os
from operator import itemgetter

import yaml

from misc.common import dict_to_prop_tree


def load_yaml(path):
    with open(path, 'rt') as f:
        return yaml.load(f.read())


class BaseConfig:

    def __init__(self, path, default_param_values={}):
        assert os.path.isfile(path), 'config with path: {} not found'.format(path)
        self._config_as_obj = load_yaml(path)
        self._sort_dict()
        self._config = dict_to_prop_tree(self._config_as_obj)

        self._default_param_values = default_param_values

    def _sort_dict(self):
        pass

    def __getattr__(self, name):
        if hasattr(self._config, name):
            return getattr(self._config, name)
        elif name in self._default_param_values:
            return self._default_param_values[name]
        else:
            raise AttributeError(name)

    def as_obj(self):
        return self._config_as_obj


class ExperimentConfig(BaseConfig):
    
    def __init__(self, path):
        default_param_values = {
            'is_gym': False,
            'load_checkpoint': None
        }
        super().__init__(path, default_param_values)

    def _sort_dict(self):
        self._config_as_obj["actor_optim"]["schedule"].sort(key=itemgetter('limit'), reverse=True)
        self._config_as_obj["critic_optim"]["schedule"].sort(key=itemgetter('limit'), reverse=True)
        self._config_as_obj["training"]["schedule"].sort(key=itemgetter('limit'), reverse=True)

    def get_env_shapes(self):
        observation_shapes = [(self._config.env.obs_size,)]
        state_shapes = [(
            self._config.env.history_length,
            self._config.env.obs_size,)]
        action_size = self._config.env.action_size
        return observation_shapes, state_shapes, action_size


class RunAgentsConfig(BaseConfig):

    def __init__(self, path):
        super().__init__(path)
        self._exp_configs = []
        for algo_config in self:
            self._exp_configs.append(
                ExperimentConfig(algo_config.experiment_config)
            )

    def _sort_dict(self):
        self._config_as_obj.sort(key=itemgetter('algorithm_id'), reverse=True)

    def __getitem__(self, index):
        return self._config[index]

    def get_exp_configs(self):
        return self._exp_configs

    def get_exp_config(self, index):
        return self._exp_configs[index]
