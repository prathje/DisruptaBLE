/*
 * hal_platform_zephyr.c
 *
 * Description: contains the POSIX implementation of the hardware
 * abstraction layer interface for zephyr-specific functionality
 *
 */

#include "platform/hal_config.h"
#include "platform/hal_crypto.h"
#include "platform/hal_io.h"
#include "platform/hal_platform.h"
#include "platform/hal_random.h"
#include "platform/hal_time.h"
#include "platform/hal_task.h"

#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <kernel.h>

// TODO: Use <sys/reboot.h>
#include <power/reboot.h>

void hal_platform_led_pin_set(uint8_t led_identifier, int mode)
{
	/* not relevant for the POSIX implementation
	 * TODO: Implement for Zephyr
	 * */
}


void hal_platform_led_set(int led_preset)
{
	/* not relevant for the POSIX implementation
	 * TODO: Implement for Zephyr
	 * */
}

void mpu_init(void)
{
	/* currently not relevant for the POSIX implementation
	 * TODO: Implement for Zephyr
	 *
	 * */
}

void hal_platform_init(int argc, char *argv[])
{
}

__attribute__((noreturn))
void hal_platform_restart(void)
{
	// TODO: Try to close open ports (e.g. TCP, L2CAP)
	LOG("Restarting!");

	sys_reboot(SYS_REBOOT_WARM);

	__builtin_unreachable();
}