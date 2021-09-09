#include <stdarg.h>


#include <sys/printk.h>
#include "platform/hal_io.h"
#include "platform/hal_semaphore.h"

struct k_sem *print_sem;
/**
 * @brief hal_io_init Initialization of underlying OS/HW for I/O
 * @return Whether the operation was successful
 */
enum ud3tn_result hal_io_init(void) {
    print_sem = hal_semaphore_init_binary();

    if (print_sem != NULL) {
        hal_semaphore_release(print_sem);
        return UD3TN_OK;
    } else {
        return UD3TN_FAIL;
    }
}


int hal_io_message_printf(const char *format, ...) {

    hal_semaphore_take_blocking(print_sem);

    va_list vl;
    va_start(vl, format);
    vprintk(format, vl);
    va_end(vl);

    hal_semaphore_release(print_sem);

    return 0;
}