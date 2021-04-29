#include <stdarg.h>


#include <sys/printk.h>
#include "platform/hal_io.h"


/**
 * @brief hal_io_init Initialization of underlying OS/HW for I/O
 * @return Whether the operation was successful
 */
enum ud3tn_result hal_io_init(void) {
    return UD3TN_OK;
}


int hal_io_message_printf(const char *format, ...) {
    va_list vl;
    va_start(vl, format);
    vprintk(format, vl);
    va_end(vl);

    return 0;
}