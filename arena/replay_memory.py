__author__ = 'sxjscience'

import mxnet as mx
import mxnet.ndarray as nd
import numpy
import copy
from utils import *


#TODO Add Buffer between GPU and CPU to reduce the overhead of copying data
class ReplayMemory(object):
    def __init__(self, rows, cols, history_length, memory_size=1000000,
                 replay_start_size=100, state_dtype='uint8', action_dtype='uint8',
                 ctx=mx.gpu()):
        self.rng = get_numpy_rng()
        self.ctx = ctx
        self.states = numpy.zeros((memory_size, rows, cols), dtype=state_dtype)
        self.actions = numpy.zeros(memory_size, dtype=action_dtype)
        self.rewards = numpy.zeros(memory_size, dtype='float32')
        self.terminate_flags = numpy.zeros(memory_size, dtype='bool')
        self.memory_size = memory_size
        self.replay_start_size = replay_start_size
        self.history_length = history_length
        self.top = 0
        self.size = 0


    def latest_slice(self):
        if self.size >= self.history_length:
            return self.states.take(numpy.arange(self.top - self.history_length, self.top), axis=0, mode="wrap")
        else:
            assert False, "We can only slice from the replay memory if the " \
                          "replay size is larger than the length of frames we want to take" \
                          "as the input."

    @property
    def sample_enabled(self):
        return self.size > self.replay_start_size

    def clear(self):
        self.states[:] = 0
        self.actions[:] = 0
        self.rewards[:] = 0
        self.terminate_flags[:] = 0
        self.top = 0
        self.size = 0

    def copy(self):
        replay_memory = copy.copy(self)
        replay_memory.states = numpy.zeros(self.states.shape, dtype=self.states.dtype)
        replay_memory.actions = numpy.zeros(self.actions.shape, dtype=self.actions.dtype)
        replay_memory.rewards = numpy.zeros(self.rewards.shape, dtype='float32')
        replay_memory.terminate_flags = numpy.zeros(self.terminate_flags.shape, dtype='bool')
        replay_memory.states[numpy.arange(self.top-self.size, self.top), ::] = \
            self.states[numpy.arange(self.top-self.size, self.top)]
        replay_memory.actions[numpy.arange(self.top-self.size, self.top)] = \
            self.actions[numpy.arange(self.top-self.size, self.top)]
        replay_memory.rewards[numpy.arange(self.top-self.size, self.top)] = \
            self.rewards[numpy.arange(self.top-self.size, self.top)]
        replay_memory.terminate_flags[numpy.arange(self.top-self.size, self.top)] = \
            self.terminate_flags[numpy.arange(self.top-self.size, self.top)]
        return replay_memory

    def append(self, img, action, reward, terminate_flag):
        self.states[self.top, :, :] = img
        self.actions[self.top] = action
        self.rewards[self.top] = reward
        self.terminate_flags[self.top] = terminate_flag
        self.top = (self.top + 1) % self.memory_size
        if self.size < self.memory_size:
            self.size += 1

    def sample(self, batch_size):
        assert self.replay_start_size >= batch_size and self.replay_start_size >= self.history_length
        assert(0 <= self.size <= self.memory_size)
        assert(0 <= self.top <= self.memory_size)
        if self.size <= self.replay_start_size:
            raise ValueError("Size of the effective samples of the ReplayMemory must be bigger than "
                             "start_size! Currently, size=%d, start_size=%d" %(self.size, self.replay_start_size))
        #TODO Possibly states + inds for less memory access
        states = numpy.zeros((batch_size, self.history_length, self.states.shape[1], self.states.shape[2]),
                             dtype=self.states.dtype)
        actions = numpy.zeros(batch_size, dtype=self.actions.dtype)
        rewards = numpy.zeros(batch_size, dtype='float32')
        terminate_flags = numpy.zeros(batch_size, dtype='bool')
        next_states = numpy.zeros((batch_size, self.history_length, self.states.shape[1], self.states.shape[2]),
                                  dtype=self.states.dtype)
        counter = 0
        while counter < batch_size:
            index = self.rng.randint(low=self.top - self.size + 1, high=self.top - self.history_length + 1)
            transition_indices = numpy.arange(index, index + self.history_length)
            initial_indices = transition_indices - 1
            end_index = index + self.history_length - 1
            if numpy.any(self.terminate_flags.take(transition_indices[0:-1], mode='wrap')):
                # Check if terminates in the middle of the sample!
                continue
            states[counter] = self.states.take(initial_indices, axis=0, mode='wrap')
            actions[counter] = self.actions.take(end_index, mode='wrap')
            rewards[counter] = self.rewards.take(end_index, mode='wrap')
            terminate_flags[counter] = self.terminate_flags.take(end_index, mode='wrap')
            next_states[counter] = self.states.take(transition_indices, axis=0, mode='wrap')
            counter += 1
        return states, actions, rewards, next_states, terminate_flags
