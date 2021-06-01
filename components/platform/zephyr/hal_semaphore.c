/*
 * hal_semaphore.c
 *
 * Description: contains the stm32-implementation of the hardware
 * abstraction layer interface for semaphore-related functionality
 *
 */

#include "platform/hal_semaphore.h"

#include <kernel.h>
#include <stdlib.h>

struct k_sem *hal_semaphore_init_binary(void)
{
    struct k_sem *sem = malloc(sizeof(struct k_sem));

    if(sem == NULL) {
        return NULL;
    }

    k_sem_init(sem, 0, 1);
	return sem;
}

void hal_semaphore_take_blocking(struct k_sem *sem)
{
    while (k_sem_take(sem, K_FOREVER))
        ;
}

void hal_semaphore_release(struct k_sem *sem)
{
    k_sem_give(sem);
}

void hal_semaphore_poll(struct k_sem *sem)
{
    k_sem_take(sem, K_NO_WAIT);
}

void hal_semaphore_delete(struct k_sem *sem)
{
    free(sem);
}

enum ud3tn_result hal_semaphore_try_take(struct k_sem *sem, int timeout_ms)
{
    if(k_sem_take(sem, K_MSEC(timeout_ms))) {
        return UD3TN_FAIL;
    }

	return UD3TN_OK;
}
