/*
 * hal_task.c
 *
 * Description: contains the stm32-implementation of the hardware
 * abstraction layer interface for thread-related functionality
 *
 */

#include "platform/hal_task.h"

#include "ud3tn/common.h"

#include <kernel.h>

k_tid_t hal_task_create(void (*task_function)(void *), const char *task_name,
		    int task_priority, void *task_parameters,
		    size_t task_stack_size, void *task_tag)
{
	/* ensure that an actual function is provided for thread creation */
	ASSERT(task_function != NULL);

    k_thread_stack_t *stack;

    // TODO: This is currently based on https://github.com/zephyrproject-rtos/zephyr/issues/26999
    int32_t ret = k_alloc_thread_stack(task_stack_size, K_USER, &stack);

    if (ret == 0) {
        // not successful! We need to free the stack again
        return NULL;
    }

    // we can now allocate memory the thread object
    struct k_thread *new_thread = k_object_alloc(K_OBJ_THREAD);

    k_tid_t thread_id = k_thread_create(
                            new_thread,
                            stack,
                            task_stack_size + CONFIG_TEST_EXTRA_STACKSIZE,
                            (k_thread_entry_t) task_function,
                            task_parameters,
                            NULL,
                            NULL,
                            task_priority,
                            K_INHERIT_PERMS,
                            K_NO_WAIT
    );

    if (thread_id == NULL) {
        k_object_free(stack);
        k_object_free(new_thread);
        return NULL;
    }

    // TODO: How to name them?
    // TODO: How to tag them?

	return thread_id;
}

void hal_task_start_scheduler(void)
{
	// NO scheduler start required for Zephyr
}


void hal_task_delay(int delay)
{
    k_msleep(delay);
}


void hal_task_delete(k_tid_t task)
{
    struct k_thread *thread = task;
    k_thread_stack_t *thread_stack = thread->stack_obj;

    k_thread_abort(task); // TODO: Do we need to ensure that the thread is not running anymore?

    k_object_free(thread_stack);
    k_object_free(thread);
}
