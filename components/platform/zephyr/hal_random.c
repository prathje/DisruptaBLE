/*
 * hal_random.c
 *
 * Description: contains the POSIX implementation of the hardware
 * abstraction layer interface for random number gerneration functionality
 *
 */

#include "platform/hal_random.h"

#include <random/rand32.h>

void hal_random_init(void)
{
    // TODO: Init random...
}

uint32_t hal_random_get(void)
{
    return sys_rand32_get();
}
