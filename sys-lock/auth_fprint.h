#ifndef AUTH_FPRINT_H
#define AUTH_FPRINT_H

#include "sys-lock.h"

typedef struct FprintContext FprintContext;

/*
 * Initialize concurrent biometric fingerprint verification via fprintd D-Bus.
 * Returns context if device and enrolled fingers are available; NULL otherwise.
 */
FprintContext *auth_fprint_init(const char *username, int pipe_fd);

/*
 * Release fingerprint hardware claim and clean up D-Bus subscriptions.
 */
void auth_fprint_cleanup(FprintContext *ctx);

#endif /* AUTH_FPRINT_H */
