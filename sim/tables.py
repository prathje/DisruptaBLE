from pydal import Field


def init_tables(db):
    db.define_table(
        'run',
        Field('name', notnull=True),
        Field('group'),
        Field('start_ts', type='datetime', notnull=True),
        Field('end_ts', type='datetime'),
        Field('status', notnull=True),
        Field('seed', type='bigint', notnull=True),
        Field('simulation_time', type='bigint', notnull=True),
        Field('progress', type='bigint', notnull=True),
        Field('num_proxy_devices', type='integer', notnull=True),
        redefine=False
    )

    db.define_table(
        'event',
        Field('run', 'reference run', notnull=True),
        Field('type', notnull=True),
        Field('device',  type='integer', notnull=True),
        Field('us',  type='bigint', notnull=True),
        Field('data_json',  type='text', notnull=True),
        redefine=False
    )

def init_eval_tables(db):
    # Actual parsed data
    db.define_table(
        'device',
        Field('run', 'reference run', notnull=True),
        Field('number',  type='integer', notnull=True),
        Field('eid',  notnull=True),
        Field('mac_addr',  notnull=True),
        redefine=False
    )

    db.define_table(
        'conn_info',
        Field('run', 'reference run', notnull=True),
        Field('client', 'reference device', notnull=True),
        Field('peripheral', 'reference device', notnull=True),
        Field('client_rx_bytes', type='integer'),
        Field('client_tx_bytes', type='integer'),
        Field('client_channel_init_us', type='bigint'),
        Field('client_channel_up_us', type='bigint'),
        Field('client_channel_down_us', type='bigint'),
        Field('client_connection_success_us', type='bigint'),
        Field('client_connection_failure_us', type='bigint'),
        Field('client_disconnect_us', type='bigint'),
        Field('client_disconnect_reason'),
        Field('client_idle_disconnect_us', type='bigint'),
        Field('peripheral_rx_bytes', type='integer'),
        Field('peripheral_tx_bytes', type='integer'),
        Field('peripheral_channel_up_us', type='bigint'),
        Field('peripheral_channel_down_us', type='bigint'),
        Field('peripheral_connection_success_us', type='bigint'),
        Field('peripheral_connection_failure_us', type='bigint'),
        Field('peripheral_disconnect_us', type='bigint'),
        Field('peripheral_disconnect_reason', type='bigint'),
        Field('peripheral_idle_disconnect_us', type='bigint'),
        redefine=False
    )

def reset_eval_tables(db):
    eval_tables = [
        'conn_info',
        'device'    #last since every other reference this one
    ]

    for t in eval_tables:
        db[t].drop()

    db.commit()