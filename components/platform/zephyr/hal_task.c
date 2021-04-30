/*
 * hal_task.c
 *
 * Description: contains the stm32-implementation of the hardware
 * abstraction layer interface for thread-related functionality
 *
 */

#include "platform/hal_task.h"

#include "ud3tn/common.h"
#include <zephyr.h>


struct zephyr_task *hal_task_create(void (*task_function)(void *), const char *task_name,
		    int task_priority, void *task_parameters,
		    size_t task_stack_size, void *task_tag)
{
	/* ensure that an actual function is provided for thread creation */
	ASSERT(task_function != NULL);

    struct zephyr_task *task = k_malloc(sizeof(struct zephyr_task));

    // TODO: This is currently based on https://github.com/zephyrproject-rtos/zephyr/issues/26999
    int32_t ret = k_alloc_thread_stack(task_stack_size, 0, &task->stack);

    if (ret == 0) {
        // not successful! We need to free the task again
        k_free(task);
        return NULL;
    }

    task->tid = k_thread_create(
                            &task->thread,
                            task->stack,
                            task_stack_size + CONFIG_TEST_EXTRA_STACKSIZE,
                            (k_thread_entry_t) task_function,
                            task_parameters,
                            NULL,
                            NULL,
                            task_priority,
                            K_INHERIT_PERMS,
                            K_NO_WAIT
    );

    if (task->tid  == NULL) {
        k_free(task->stack);
        k_free(task);
        return NULL;
    }

    // TODO: How to name them?
    // TODO: How to tag them?

	return task;
}

void hal_task_start_scheduler(void)
{
	// NO scheduler start required for Zephyr
}

void hal_task_delay(int delay)
{
    k_msleep(delay);
}


void hal_task_delete(struct zephyr_task *task)
{
    k_thread_abort(task->tid); // TODO: Do we need to ensure that the thread is not running anymore?
    k_free(task->stack);
    k_free(task);
}
