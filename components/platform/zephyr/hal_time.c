/*
 * hal_time.c
 *
 * Description: contains the POSIX implementation of the hardware
 * abstraction layer interface for time-related functionality
 *
 */

#include "platform/hal_time.h"
#include "platform/hal_semaphore.h"


#include <kernel.h>

#include <stdlib.h>
#include <stdio.h>
#include <stdbool.h>
#include <time.h>
#include <math.h>
#include <string.h>


static int64_t ref_ticks;
static uint64_t ref_timestamp;

static char *time_string;
static Semaphore_t time_string_semph;

void hal_time_init(const uint64_t initial_timestamp)
{
    ref_ticks = k_uptime_ticks();
    ref_timestamp = initial_timestamp;
}

uint64_t hal_time_get_timestamp_s(void)
{
    return ref_timestamp + (uint64_t)((k_uptime_ticks() - ref_ticks) / CONFIG_SYS_CLOCK_TICKS_PER_SEC);
}

uint64_t hal_time_get_timestamp_ms(void)
{
    return ref_timestamp * 1000ULL + k_ticks_to_ms_floor64(k_uptime_ticks() - ref_ticks);
}

uint64_t hal_time_get_timestamp_us(void)
{
    return ref_timestamp * 1000000ULL + k_ticks_to_us_floor64(k_uptime_ticks() - ref_ticks);
}


uint64_t hal_time_get_system_time(void)
{
    return k_ticks_to_us_floor64(k_uptime_ticks());
}

char *hal_time_get_log_time_string(void)
{
    char *tmp_string;

    if (time_string == NULL) {
        time_string_semph = hal_semaphore_init_binary();
        time_string = malloc(64);
        time_string[63] = '\0';
    } else {
        hal_semaphore_take_blocking(time_string_semph);
    }

    snprintf(time_string, 64, "%llu",
             (unsigned long long) hal_time_get_timestamp_s());

    hal_semaphore_release(time_string_semph);

    tmp_string = time_string;

    return tmp_string;
}