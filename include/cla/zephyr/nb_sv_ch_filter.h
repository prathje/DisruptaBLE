#ifndef NB_SV_CH_FILTER_INCLUDE_H
#define NB_SV_CH_FILTER_INCLUDE_H

#include "routing/epidemic/summary_vector.h"

void nb_sv_ch_filter_init();
void nb_sv_ch_filter_add(struct summary_vector_characteristic *sv_ch);
bool nb_sv_ch_filter_contains(struct summary_vector_characteristic *sv_ch);

#endif