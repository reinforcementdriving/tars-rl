#!/usr/bin/env python

import gym
import numpy as np

class LunarLander:

    def __init__(self, frame_skip=1):
        self.env = gym.make('LunarLanderContinuous-v2')
        self.frame_skip = frame_skip
        self.observation_shapes = [(8,)]
        self.action_size = 2

    def reset(self):
        self.time_step = 0
        self.total_reward = 0
        self.init_action = np.round(np.random.uniform(-1.0, 1.0, size=self.action_size))
        return self.env.reset()

    def step(self, action):
        reward = 0
        for i in range(self.frame_skip):
            observation, r, done, info = self.env.step(action) 
            reward += r*1e-2
            if done: break
        self.total_reward += reward
        self.time_step += 1
        return observation, reward, done, info

    def get_total_reward(self):
        return self.total_reward
    
    def get_random_action(self, resample=True):
        if resample:
            self.init_action = np.round(np.random.uniform(-1.0, 1.0, size=self.action_size))
        return self.init_action

