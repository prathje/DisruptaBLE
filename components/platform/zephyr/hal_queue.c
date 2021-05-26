#include "platform/hal_queue.h"
#include "ud3tn/result.h"
#include "platform/hal_io.h"

#include <kernel.h>
#include <stdlib.h>
/**
 * @brief hal_queue_create Creates a new channel for inter-task communication
 * @param queueLength The maximum number of items than can be stored inside
 *                    the queue
 * @param itemSize The size of one item in bytes
 * @return A queue identifier
 */
struct k_msgq *hal_queue_create(int queue_length, int item_size) {

    struct k_msgq * queue = malloc(sizeof(struct k_msgq));
    if (queue == NULL) {
        return NULL;
    }

    int ret = k_msgq_alloc_init(queue, item_size, queue_length);

    if (ret) {
        // not successfull!
        free(queue);
        return NULL;
    }

    return queue;
}


/**
 * @brief hal_queue_delete Deletes a specified queue and frees its memory
 * @param queue The queue that should be deleted
 */
void hal_queue_delete(struct k_msgq *queue) {
    k_msgq_cleanup(queue);
    free(queue);
}

/**
 * @brief hal_queue_push_to_back Attach a given item to the back of the queue.
 *                            Has blocking behaviour, i.e. tries to insert
 *                            the element in the underlying OS structure
 *                            indefinitely
 * @param queue The identifier of the Queue that the element should be
 *              inserted
 * @param item  The target item
 */
void hal_queue_push_to_back(struct k_msgq *queue, const void *item) {
    int ret = k_msgq_put(queue, item, K_FOREVER);

    if(ret) {
        hal_io_message_printf("Error in hal_queue_push_to_back");
    }
}

/**
 * @brief hal_queue_try_push_to_back Attach a given item to the back of the
 *			      queue.
 *                            Has blocking behaviour, i.e. tries to insert
 *                            the element in the underlying OS structure
 *                            indefinitely
 * @param queue The identifier of the Queue that the element should be
 *              inserted
 * @param item  The target item
 * @param timeout After which time (in milliseconds) the receiving attempt
 *		  should be aborted.
 *		  If this value is -1, receiving will block indefinitely
 * @return Whether the attachment attempt was successful
 */
enum ud3tn_result hal_queue_try_push_to_back(struct k_msgq *queue,
                                             const void *item,
                                             int timeout) {
    int ret = k_msgq_put(queue, item, K_MSEC(timeout));

    if(ret) {
        if (-ret != EAGAIN) {
            hal_io_message_printf("Error in hal_queue_push_to_back");
        }
        return UD3TN_FAIL;
    } else {
        return UD3TN_OK;
    }
}

/**
 * @brief hal_queue_override_to_back Attach a given item to the back of the
 *			      queue. If there is no space available, override
 *			      previous elements
 * @param queue The identifier of the Queue that the element should be
 *              inserted
 * @param item  The target item
 * @return Whether the attachment attempt was successful --> that is per
 *	   functionality of this function always true!
 */
enum ud3tn_result hal_queue_override_to_back(struct k_msgq *queue,
                                             const void *item) {
    while (k_msgq_put(queue, &item, K_NO_WAIT) != 0) {
        /* message queue is full: purge old data & try again */
        k_msgq_purge(queue);
    }
    return UD3TN_OK;
}

/**
 * @brief hal_queue_receive Receive a item from the specific queue
 *			    Has blocking behaviour!
 * @param queue The identifier of the Queue that the element should be read
 *		from
 * @param targetBuffer A pointer to the memory where the received item should
 *		       be stored
 * @param timeout After which time (in milliseconds) the receiving attempt
 *		  should be aborted.
 *		  If this value is -1, receiving will block indefinitely
 * @return Whether the receiving was successful
 */
enum ud3tn_result hal_queue_receive(struct k_msgq *queue,
                                    void *targetBuffer,
                                    int timeout) {

    k_timeout_t zephyr_timeout = timeout == -1 ? K_FOREVER : K_MSEC(timeout);

    int ret = k_msgq_get(queue, targetBuffer, zephyr_timeout);

    return ret == 0 ? UD3TN_OK : UD3TN_FAIL;
}

/**
 * @brief hal_queue_reset Reset (i.e. empty) the specific queue
 * @param queue The queue that should be cleared
 */
void hal_queue_reset(struct k_msgq *queue) {
    k_msgq_purge(queue);
}

/**
 * @brief hal_queue_nr_of_data_waiting Return the number of waiting items
 *				       in a queue
 * @param The queue that should be checked
 * @return 0 if the queue doesn't exist, otherwise the number of waiting
 *	     items
 */
uint8_t hal_queue_nr_of_items_waiting(struct k_msgq *queue) {
    return k_msgq_num_used_get(queue);
}
