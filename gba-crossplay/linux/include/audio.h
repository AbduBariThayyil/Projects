#ifndef GBA_CROSSPLAY_AUDIO_H
#define GBA_CROSSPLAY_AUDIO_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

bool gba_audio_init(int sample_rate, int channels);
void gba_audio_deinit(void);

/* Feeds 16-bit interleaved stereo PCM samples to SDL audio queue */
void gba_audio_feed(const int16_t* samples, size_t sample_count, bool is_turbo);

/* Resets/clears audio buffer */
void gba_audio_clear(void);

#ifdef __cplusplus
}
#endif

#endif /* GBA_CROSSPLAY_AUDIO_H */
