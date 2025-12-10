#!/usr/bin/env python3
"""Test sound playback on Pi"""
import os
os.environ['SDL_AUDIODRIVER'] = 'alsa'

import pygame
import numpy as np
import time

pygame.init()
print('Mixer info:', pygame.mixer.get_init())

sample_rate = 22050
duration = 0.5
t = np.linspace(0, duration, int(sample_rate * duration), False)
wave = np.sin(2 * np.pi * 440 * t) * 0.5
wave = (wave * 32767).astype(np.int16)

# Convert to stereo
stereo_wave = np.column_stack((wave, wave))
print('Wave shape:', stereo_wave.shape)

snd = pygame.sndarray.make_sound(stereo_wave)
snd.set_volume(1.0)
print('Playing test tone (you should hear 440Hz for 0.5 seconds)...')
snd.play()
time.sleep(1)
print('Done')
pygame.quit()
