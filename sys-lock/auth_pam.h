#ifndef AUTH_PAM_H
#define AUTH_PAM_H

#include "sys-lock.h"

/*
 * Asynchronously verify password against PAM (detached pthread).
 * Sends MSG_PAM_SUCCESS or MSG_PAM_FAILURE via pipe_fd.
 * Ensures zero-trace password security via explicit_bzero.
 */
int auth_pam_verify_async(const char *username, const char *password, int pipe_fd);

#endif /* AUTH_PAM_H */
