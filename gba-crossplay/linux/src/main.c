#include "emulator.h"
#include "audio.h"
#include "discovery.h"
#include "hud.h"
#include "../../core/link_protocol.h"

#include <SDL2/SDL.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <sys/time.h>

#include <mgba/internal/gba/input.h>

static volatile bool g_running = true;

static void sigint_handler(int sig) {
    (void)sig;
    g_running = false;
}

static uint64_t get_time_us(void) {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (uint64_t)(tv.tv_sec * 1000000 + tv.tv_usec);
}

int main(int argc, char** argv) {
    if (argc < 2) {
        printf("Usage: %s <rom.gba> [options]\n", argv[0]);
        printf("Options:\n");
        printf("  --host [port]      Host multiplayer server (default port %d)\n", GBA_LINK_DEFAULT_PORT);
        printf("  --join <ip> [port] Join remote host (default port %d)\n", GBA_LINK_DEFAULT_PORT);
        printf("  --turbo <2|3>      Set fast-forward multiplier (default 2)\n");
        printf("  --headless         Run without window/audio (for testing/automation)\n");
        return 1;
    }

    signal(SIGINT, sigint_handler);

    const char* rom_path = argv[1];
    bool is_host = true;
    char remote_ip[64] = "127.0.0.1";
    uint16_t port = GBA_LINK_DEFAULT_PORT;
    uint8_t turbo_mult = 2;
    bool headless = false;

    for (int i = 2; i < argc; i++) {
        if (strcmp(argv[i], "--host") == 0) {
            is_host = true;
            if (i + 1 < argc && argv[i + 1][0] != '-') {
                port = (uint16_t)atoi(argv[++i]);
            }
        } else if (strcmp(argv[i], "--join") == 0) {
            is_host = false;
            if (i + 1 < argc && argv[i + 1][0] != '-') {
                strncpy(remote_ip, argv[++i], sizeof(remote_ip) - 1);
            }
            if (i + 1 < argc && argv[i + 1][0] != '-') {
                port = (uint16_t)atoi(argv[++i]);
            }
        } else if (strcmp(argv[i], "--turbo") == 0 && i + 1 < argc) {
            turbo_mult = (uint8_t)atoi(argv[++i]);
        } else if (strcmp(argv[i], "--headless") == 0) {
            headless = true;
        }
    }

    int socket_fd = -1;
    int listen_fd = -1;
    uint8_t player_id = is_host ? 0 : 1;

    if (is_host) {
        listen_fd = socket(AF_INET, SOCK_STREAM, 0);
        if (listen_fd >= 0) {
            int reuse = 1;
            setsockopt(listen_fd, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));

            struct sockaddr_in addr;
            memset(&addr, 0, sizeof(addr));
            addr.sin_family = AF_INET;
            addr.sin_port = htons(port);
            addr.sin_addr.s_addr = htonl(INADDR_ANY);

            if (bind(listen_fd, (struct sockaddr*)&addr, sizeof(addr)) == 0) {
                listen(listen_fd, 1);
                /* Non-blocking listen */
                int flags = fcntl(listen_fd, F_GETFL, 0);
                fcntl(listen_fd, F_SETFL, flags | O_NONBLOCK);
                printf("[GBA-Crossplay] Hosting on port %d... Beacon active.\n", port);
                gba_discovery_start_beacon("GBA Game", port);
            }
        }
    } else {
        printf("[GBA-Crossplay] Connecting to %s:%d...\n", remote_ip, port);
        socket_fd = socket(AF_INET, SOCK_STREAM, 0);
        if (socket_fd >= 0) {
            struct sockaddr_in addr;
            memset(&addr, 0, sizeof(addr));
            addr.sin_family = AF_INET;
            addr.sin_port = htons(port);
            inet_pton(AF_INET, remote_ip, &addr.sin_addr);

            if (connect(socket_fd, (struct sockaddr*)&addr, sizeof(addr)) == 0) {
                printf("[GBA-Crossplay] Connected to host successfully!\n");
            } else {
                printf("[GBA-Crossplay] Waiting for host or offline mode...\n");
            }
        }
    }

    /* Initialize SDL */
    SDL_Window* window = NULL;
    SDL_Renderer* renderer = NULL;
    SDL_Texture* texture = NULL;
    SDL_GameController* controller = NULL;

    if (!headless) {
        if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_GAMECONTROLLER) < 0) {
            fprintf(stderr, "SDL Init failed: %s\n", SDL_GetError());
            return 1;
        }

        window = SDL_CreateWindow("GBA Crossplay [Arch Linux]",
                                  SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                                  720, 480, SDL_WINDOW_RESIZABLE);
        if (!window) {
            fprintf(stderr, "Window creation failed: %s\n", SDL_GetError());
            return 1;
        }

        renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED);
        if (!renderer) {
            renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_SOFTWARE);
        }

        texture = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_ABGR8888,
                                    SDL_TEXTUREACCESS_STREAMING,
                                    GBA_VIDEO_WIDTH, GBA_VIDEO_HEIGHT);

        gba_audio_init(44100, 2);

        /* Open first available gamepad */
        for (int i = 0; i < SDL_NumJoysticks(); i++) {
            if (SDL_IsGameController(i)) {
                controller = SDL_GameControllerOpen(i);
                if (controller) {
                    printf("[GBA-Crossplay] Gamepad connected: %s\n", SDL_GameControllerName(controller));
                    break;
                }
            }
        }
    }

    /* Initialize Emulator Core */
    GBAEmulator* emu = gba_emulator_create(rom_path, player_id, socket_fd);
    if (!emu) {
        fprintf(stderr, "Failed to initialize GBA core.\n");
        if (!headless) SDL_Quit();
        return 1;
    }

    GBATurboCoordinator* turbo = gba_emulator_get_turbo(emu);
    if (turbo && turbo_mult > 1) {
        turbo->multiplier = turbo_mult;
    }

    GBAHUDState hud;
    memset(&hud, 0, sizeof(hud));
    hud.connected = (socket_fd >= 0);
    hud.player_id = player_id;
    hud.total_players = 2;
    snprintf(hud.remote_ip, sizeof(hud.remote_ip), "%s", remote_ip);
    hud.turbo_multiplier = turbo_mult;
    hud.show_hud = true;

    uint32_t keys = 0;
    uint64_t last_frame_time = get_time_us();
    uint64_t fps_timer = last_frame_time;
    int frame_count = 0;

    printf("[GBA-Crossplay] Running game: %s\n", gba_emulator_get_title(emu));

    while (g_running) {
        /* Check incoming connection for host */
        if (is_host && socket_fd < 0 && listen_fd >= 0) {
            struct sockaddr_in client_addr;
            socklen_t client_len = sizeof(client_addr);
            int new_fd = accept(listen_fd, (struct sockaddr*)&client_addr, &client_len);
            if (new_fd >= 0) {
                socket_fd = new_fd;
                char client_ip[64];
                inet_ntop(AF_INET, &client_addr.sin_addr, client_ip, sizeof(client_ip));
                printf("[GBA-Crossplay] Peer connected from %s!\n", client_ip);
                snprintf(hud.remote_ip, sizeof(hud.remote_ip), "%s", client_ip);
                hud.connected = true;
            }
        }

        if (!headless) {
            SDL_Event ev;
            while (SDL_PollEvent(&ev)) {
                if (ev.type == SDL_QUIT) {
                    g_running = false;
                } else if (ev.type == SDL_KEYDOWN || ev.type == SDL_KEYUP) {
                    bool down = (ev.type == SDL_KEYDOWN);
                    switch (ev.key.keysym.sym) {
                        case SDLK_x:         down ? (keys |= (1 << GBA_KEY_A)) : (keys &= ~(1 << GBA_KEY_A)); break;
                        case SDLK_z:         down ? (keys |= (1 << GBA_KEY_B)) : (keys &= ~(1 << GBA_KEY_B)); break;
                        case SDLK_a:         down ? (keys |= (1 << GBA_KEY_L)) : (keys &= ~(1 << GBA_KEY_L)); break;
                        case SDLK_s:         down ? (keys |= (1 << GBA_KEY_R)) : (keys &= ~(1 << GBA_KEY_R)); break;
                        case SDLK_RETURN:    down ? (keys |= (1 << GBA_KEY_START)) : (keys &= ~(1 << GBA_KEY_START)); break;
                        case SDLK_BACKSPACE: down ? (keys |= (1 << GBA_KEY_SELECT)) : (keys &= ~(1 << GBA_KEY_SELECT)); break;
                        case SDLK_UP:        down ? (keys |= (1 << GBA_KEY_UP)) : (keys &= ~(1 << GBA_KEY_UP)); break;
                        case SDLK_DOWN:      down ? (keys |= (1 << GBA_KEY_DOWN)) : (keys &= ~(1 << GBA_KEY_DOWN)); break;
                        case SDLK_LEFT:      down ? (keys |= (1 << GBA_KEY_LEFT)) : (keys &= ~(1 << GBA_KEY_LEFT)); break;
                        case SDLK_RIGHT:     down ? (keys |= (1 << GBA_KEY_RIGHT)) : (keys &= ~(1 << GBA_KEY_RIGHT)); break;
                        case SDLK_TAB:       gba_turbo_set_local(turbo, down); break;
                        case SDLK_F1:        if (down) hud.show_hud = !hud.show_hud; break;
                        case SDLK_ESCAPE:    g_running = false; break;
                        default: break;
                    }
                } else if (ev.type == SDL_CONTROLLERBUTTONDOWN || ev.type == SDL_CONTROLLERBUTTONUP) {
                    bool down = (ev.type == SDL_CONTROLLERBUTTONDOWN);
                    switch (ev.cbutton.button) {
                        case SDL_CONTROLLER_BUTTON_A:             down ? (keys |= (1 << GBA_KEY_A)) : (keys &= ~(1 << GBA_KEY_A)); break;
                        case SDL_CONTROLLER_BUTTON_B:             down ? (keys |= (1 << GBA_KEY_B)) : (keys &= ~(1 << GBA_KEY_B)); break;
                        case SDL_CONTROLLER_BUTTON_LEFTSHOULDER:  down ? (keys |= (1 << GBA_KEY_L)) : (keys &= ~(1 << GBA_KEY_L)); break;
                        case SDL_CONTROLLER_BUTTON_RIGHTSHOULDER: down ? (keys |= (1 << GBA_KEY_R)) : (keys &= ~(1 << GBA_KEY_R)); break;
                        case SDL_CONTROLLER_BUTTON_START:         down ? (keys |= (1 << GBA_KEY_START)) : (keys &= ~(1 << GBA_KEY_START)); break;
                        case SDL_CONTROLLER_BUTTON_BACK:          down ? (keys |= (1 << GBA_KEY_SELECT)) : (keys &= ~(1 << GBA_KEY_SELECT)); break;
                        case SDL_CONTROLLER_BUTTON_DPAD_UP:       down ? (keys |= (1 << GBA_KEY_UP)) : (keys &= ~(1 << GBA_KEY_UP)); break;
                        case SDL_CONTROLLER_BUTTON_DPAD_DOWN:     down ? (keys |= (1 << GBA_KEY_DOWN)) : (keys &= ~(1 << GBA_KEY_DOWN)); break;
                        case SDL_CONTROLLER_BUTTON_DPAD_LEFT:     down ? (keys |= (1 << GBA_KEY_LEFT)) : (keys &= ~(1 << GBA_KEY_LEFT)); break;
                        case SDL_CONTROLLER_BUTTON_DPAD_RIGHT:    down ? (keys |= (1 << GBA_KEY_RIGHT)) : (keys &= ~(1 << GBA_KEY_RIGHT)); break;
                        case SDL_CONTROLLER_BUTTON_MISC1:         gba_turbo_set_local(turbo, down); break;
                        default: break;
                    }
                }
            }
        }

        gba_emulator_set_keys(emu, keys);
        gba_emulator_step_frame(emu);

        hud.is_turbo = gba_turbo_is_active(turbo);
        frame_count++;

        uint64_t now = get_time_us();
        if (now - fps_timer >= 1000000) {
            hud.current_fps = (float)frame_count;
            frame_count = 0;
            fps_timer = now;
        }

        if (!headless && renderer && texture) {
            int win_w, win_h;
            SDL_GetWindowSize(window, &win_w, &win_h);

            /* Update GBA screen texture */
            const uint32_t* pixels = gba_emulator_get_pixels(emu);
            if (pixels) {
                SDL_UpdateTexture(texture, NULL, pixels, GBA_VIDEO_WIDTH * sizeof(uint32_t));
            }

            SDL_SetRenderDrawColor(renderer, 10, 10, 12, 255);
            SDL_RenderClear(renderer);

            /* Calculate 3:2 aspect ratio destination rect */
            int scale_x = win_w / GBA_VIDEO_WIDTH;
            int scale_y = win_h / GBA_VIDEO_HEIGHT;
            int scale = (scale_x < scale_y) ? scale_x : scale_y;
            if (scale < 1) scale = 1;

            int dst_w = GBA_VIDEO_WIDTH * scale;
            int dst_h = GBA_VIDEO_HEIGHT * scale;
            SDL_Rect dst_rect = { (win_w - dst_w) / 2, (win_h - dst_h) / 2, dst_w, dst_h };

            SDL_RenderCopy(renderer, texture, NULL, &dst_rect);

            /* Draw HUD overlay */
            gba_hud_draw(renderer, win_w, win_h, &hud);

            SDL_RenderPresent(renderer);
        }

        /* Timing: Lock to target frame time (16.7ms for 1x, 8.3ms for 2x turbo) */
        uint32_t target_delay = gba_turbo_get_frame_us(turbo);
        uint64_t elapsed = get_time_us() - last_frame_time;
        if (elapsed < target_delay) {
            usleep(target_delay - elapsed);
        }
        last_frame_time = get_time_us();
    }

    printf("[GBA-Crossplay] Cleaning up and exiting...\n");

    gba_discovery_stop_beacon();
    if (socket_fd >= 0) close(socket_fd);
    if (listen_fd >= 0) close(listen_fd);

    gba_emulator_destroy(emu);
    if (!headless) {
        gba_audio_deinit();
        if (controller) SDL_GameControllerClose(controller);
        if (texture) SDL_DestroyTexture(texture);
        if (renderer) SDL_DestroyRenderer(renderer);
        if (window) SDL_DestroyWindow(window);
        SDL_Quit();
    }

    return 0;
}
