#include "ud3tn/cmdline.h"
#include "ud3tn/init.h"


int u3dtn_main(int argc, char *argv[]) {
    init(argc, argv);
    start_tasks(parse_cmdline(argc, argv));
    return start_os();
}


#ifdef __ZEPHYR__
#include <zephyr.h>
void main(void) {
    int argc = 0;
    char * argv[] = {};
    u3dtn_main(argc, argv);
}
#else
int main(int argc, char *argv[]) {
    return u3dtn_main(argc, argv);
}
#endif