#include "audio.h"
#include <SDL2/SDL.h>
#include <stdio.h>

static SDL_AudioDeviceID g_audio_dev = 0;
static int g_sample_rate = 44100;
static int g_channels = 2;

bool gba_audio_init(int sample_rate, int channels) {
    if (g_audio_dev != 0) return true;

    if (SDL_InitSubSystem(SDL_INIT_AUDIO) < 0) {
        fprintf(stderr, "SDL Audio init failed: %s\n", SDL_GetError());
        return false;
    }

    g_sample_rate = sample_rate;
    g_channels = channels;

    SDL_AudioSpec desired, obtained;
    SDL_zero(desired);
    desired.freq = sample_rate;
    desired.format = AUDIO_S16SYS;
    desired.channels = (Uint8)channels;
    desired.samples = 1024;

    g_audio_dev = SDL_OpenAudioDevice(NULL, 0, &desired, &obtained, 0);
    if (g_audio_dev == 0) {
        fprintf(stderr, "SDL OpenAudioDevice failed: %s\n", SDL_GetError());
        return false;
    }

    SDL_PauseAudioDevice(g_audio_dev, 0); /* Unpause */
    return true;
}

void gba_audio_deinit(void) {
    if (g_audio_dev != 0) {
        SDL_CloseAudioDevice(g_audio_dev);
        g_audio_dev = 0;
    }
}

void gba_audio_feed(const int16_t* samples, size_t sample_count, bool is_turbo) {
    if (g_audio_dev == 0 || !samples || sample_count == 0) return;

    size_t bytes = sample_count * sizeof(int16_t) * g_channels;

    Uint32 queued = SDL_GetQueuedAudioSize(g_audio_dev);
    /* Prevent buffer bloat, especially when turbo is accelerating */
    Uint32 max_queued = (Uint32)(g_sample_rate * sizeof(int16_t) * g_channels * (is_turbo ? 0.05 : 0.15));

    if (queued > max_queued) {
        /* Drop samples or clear excess to maintain low-latency sync */
        SDL_ClearQueuedAudio(g_audio_dev);
    }

    SDL_QueueAudio(g_audio_dev, samples, (Uint32)bytes);
}

void gba_audio_clear(void) {
    if (g_audio_dev != 0) {
        SDL_ClearQueuedAudio(g_audio_dev);
    }
}
