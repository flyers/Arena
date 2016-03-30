__author__ = 'sxjscience'

from ale_python_interface import ALEInterface
import mxnet as mx
import numpy
import cv2
import logging
import os
from arena.utils import *
from arena import ReplayMemory
from .game import Game
from .game import DEFAULT_MAX_EPISODE_STEP
import time
logger = logging.getLogger(__name__)

_dirname = os.path.dirname(os.path.realpath(__file__))
_default_rom_path = os.path.join(_dirname, "roms", "breakout.bin")


def ale_load_from_rom(rom_path, display_screen):
    rng = get_numpy_rng()
    ale = ALEInterface()
    ale.setInt('random_seed', rng.randint(1000))
    if display_screen:
        import sys
        if sys.platform == 'darwin':
            import pygame
            pygame.init()
            ale.setBool('sound', False) # Sound doesn't work on OSX
        ale.setBool('display_screen', True)
    else:
        ale.setBool('display_screen', False)
    ale.setFloat('repeat_action_probability', 0)
    ale.loadROM(rom_path)
    return ale


class AtariGame(Game):
    def __init__(self,
                 rom_path=_default_rom_path,
                 frame_skip=4, history_length=4,
                 resize_mode='scale', resized_rows=84, resized_cols=84, crop_offset=8,
                 display_screen=False, max_null_op=30,
                 replay_memory_size=1000000,
                 replay_start_size=100,
                 death_end_episode=True):
        super(AtariGame, self).__init__()
        self.rng = get_numpy_rng()
        self.ale = ale_load_from_rom(rom_path=rom_path, display_screen=display_screen)
        self.start_lives = self.ale.lives()
        self.action_set = self.ale.getMinimalActionSet()
        self.resize_mode = resize_mode
        self.resized_rows = resized_rows
        self.resized_cols = resized_cols
        self.crop_offset = crop_offset
        self.frame_skip = frame_skip
        self.history_length = history_length
        self.max_null_op = max_null_op
        self.death_end_episode = death_end_episode
        self.screen_buffer_length = 2
        self.screen_buffer = numpy.empty((self.screen_buffer_length,
                                          self.ale.getScreenDims()[1], self.ale.getScreenDims()[0]),
                                         dtype='uint8')
        self.replay_memory = ReplayMemory(state_dim=(resized_rows, resized_cols),
                                              history_length=history_length,
                                              memory_size=replay_memory_size,
                                              replay_start_size=replay_start_size)

        self.start()

    def start(self):
        self.ale.reset_game()
        null_op_num = self.rng.randint(self.screen_buffer_length,
                                       max(self.max_null_op + 1, self.screen_buffer_length + 1))
        for i in range(null_op_num):
            self.ale.act(0)
            self.ale.getScreenGrayscale(self.screen_buffer[i % self.screen_buffer_length, :, :])
        self.total_reward = 0
        self.episode_reward = 0
        self.episode_step = 0
        self.max_episode_step = DEFAULT_MAX_EPISODE_STEP
        self.start_lives = self.ale.lives()

    def force_restart(self):
        self.start()
        self.replay_memory.clear()

    '''
    Call this to begin an episode of a game instance.
    Here, we can play the game for a maximum of `max_episode_step` and after that, we are force to
    '''
    def begin_episode(self, max_episode_step=DEFAULT_MAX_EPISODE_STEP):
        # We need to restart the environment if our current counting is larger than the max episode_step
        if self.episode_step > self.max_episode_step or self.ale.game_over():
            self.start()
        else:
            for i in range(self.screen_buffer_length):
                self.ale.act(0)
                self.ale.getScreenGrayscale(self.screen_buffer[i % self.screen_buffer_length, :, :])
        self.max_episode_step = max_episode_step
        self.start_lives = self.ale.lives()
        self.episode_reward = 0
        self.episode_step = 0

    @property
    def episode_terminate(self):
        termination_flag = self.ale.game_over() or self.episode_step >= self.max_episode_step
        if self.death_end_episode:
            return (self.ale.lives() < self.start_lives) or termination_flag
        else:
            return termination_flag

    def get_observation(self):
        image = self.screen_buffer.max(axis=0)
        if 'crop' == self.resize_mode:
            original_rows, original_cols = image.shape
            new_resized_rows = int(round(
                float(original_rows) * self.resized_cols / original_cols))
            resized = cv2.resize(image, (self.resized_cols, new_resized_rows),
                                 interpolation=cv2.INTER_LINEAR)
            crop_y_cutoff = new_resized_rows - self.crop_offset - self.resized_rows
            img = resized[crop_y_cutoff:
            crop_y_cutoff + self.resized_rows, :]
            return img
        else:
            return cv2.resize(image, (self.resized_cols, self.resized_rows),
                              interpolation=cv2.INTER_LINEAR)

    def play(self, a):
        assert not self.episode_terminate, "Warning, the episode seems to have terminated. " \
                                           "We need to call either game.begin_episode(max_episode_step) to continue a new episode" \
                                           "or game.start() to force restart."
        self.episode_step += 1
        reward = 0.0
        action = self.action_set[a]
        for i in xrange(self.frame_skip):
            reward += self.ale.act(action)
            self.ale.getScreenGrayscale(self.screen_buffer[i % self.screen_buffer_length, :, :])
        self.total_reward += reward
        self.episode_reward += reward
        ob = self.get_observation()
        terminate_flag = self.episode_terminate
        self.replay_memory.append(ob, a, numpy.clip(reward, -1, 1), terminate_flag)
        return reward, terminate_flag
