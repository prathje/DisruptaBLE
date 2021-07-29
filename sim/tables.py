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
        Field('configuration_json', type='text', notnull=True),
        redefine=True,
        migrate=False
    )

    db.define_table(
        'event',
        Field('run', 'reference run', notnull=True),
        Field('type', notnull=True),
        Field('device', type='integer', notnull=True),
        Field('us', type='bigint', notnull=True),
        Field('data_json', type='text', notnull=True),
        redefine=True,
        migrate=False
    )

    db.executesql('CREATE INDEX IF NOT EXISTS type_index ON event (type);')
    db.executesql('''
        CREATE OR REPLACE VIEW pos_pair
        AS SELECT pa.run as run, pa.us as us, pc.us as us_next, pa.device as device_a, pb.device as device_b, pa.pos_x as pa_x, pa.pos_y as pa_y, pb.pos_x as pb_x, pb.pos_y as pb_y, pc.pos_x as pc_x, pc.pos_y as pc_y, pd.pos_x as pd_x, pd.pos_y as pd_y
        FROM position pa
        JOIN position pb ON pa.run = pb.run AND pb.us = pa.us
        LEFT JOIN position pc ON pc.device = pa.device AND pc.us = (pa.us + 1000000)
        LEFT JOIN position pd ON pd.device = pb.device AND pd.us = (pb.us + 1000000);
    ''')

    db.executesql('''
        CREATE OR REPLACE VIEW distance_pair
        AS SELECT pa.run as run, pa.us as us, pa.us_next as us_next, pa.device_a as device_a, pa.device_b as device_b,
        SQRT( POWER(pa.pa_x - pa.pb_x, 2) + POWER(pa.pa_y - pa.pb_y, 2)) as d,
        SQRT( POWER(pa.pc_x - pa.pd_x, 2) + POWER(pa.pc_y - pa.pd_y, 2)) as d_next
        FROM pos_pair pa;
    ''')

    db.executesql(
    '''
        CREATE OR REPLACE VIEW bundle_reception
        AS
        SELECT bt.run as run, bt.id as bundle_transmission, MIN(bt.end_us) as us, b.id as bundle, ssb.device as source_device, rsb.device as device, d.eid as receiver_eid, b.destination_eid as destination_eid         
        FROM bundle_transmission bt
        JOIN stored_bundle ssb ON ssb.id = bt.source_stored_bundle
        JOIN stored_bundle rsb ON rsb.id = bt.received_stored_bundle
        JOIN device d ON d.id = rsb.device
        JOIN bundle b ON b.id = ssb.bundle
         WHERE bt.end_us IS NOT NULL
          GROUP BY b.id, rsb.device
    ''')


def init_eval_tables(db):
    # Actual parsed data
    db.define_table(
        'device',
        Field('run', 'reference run', notnull=True),
        Field('number', type='integer', notnull=True),
        Field('eid', notnull=True),
        Field('mac_addr', notnull=True),
        redefine=True,
        migrate=False
    )

    db.define_table(
        'conn_info',
        Field('run', 'reference run', notnull=True),
        Field('client', 'reference device', notnull=True),
        Field('peripheral', 'reference device', notnull=True),
        Field('client_rx_bytes', type='integer'),
        Field('client_tx_bytes', type='integer'),
        Field('client_conn_init_us', type='bigint'),
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
        redefine=True,
        migrate=False
    )

    db.define_table(
        'bundle',
        Field('run', 'reference run', notnull=True),
        Field('source', 'reference device', notnull=True),
        Field('destination_eid'),
        Field('source_eid'),
        Field('destination', 'reference device', notnull=False),
        Field('creation_timestamp_ms', type='integer'),
        Field('sequence_number', type='integer'),
        Field('payload_length', type='integer'),
        Field('is_sv', type='boolean'),
        Field('lifetime_ms', type='integer'),
        Field('hop_count', type='integer'),
        redefine=True,
        migrate=False
    )

    db.define_table(
        'stored_bundle',
        Field('run', 'reference run', notnull=True),
        Field('device', 'reference device', notnull=True),
        Field('bundle', 'reference bundle', notnull=True),
        Field('created_us', type='bigint', notnull=True),
        Field('local_id', type='integer', notnull=True),
        Field('deleted_us', type='bigint', notnull=False),
        Field('remaining_hops', type='integer', notnull=False),
        redefine=True,
        migrate=False
    )

    db.define_table(
        'bundle_transmission',
        Field('run', 'reference run', notnull=True),
        Field('conn_info', 'reference conn_info', notnull=True),
        Field('source_stored_bundle', 'reference stored_bundle', notnull=True),
        Field('received_stored_bundle', 'reference stored_bundle', notnull=False),
        Field('start_us', type='bigint'),
        Field('end_us', type='bigint'),
        redefine=True,
        migrate=False
    )

    db.define_table(
        'advertisements',
        Field('run', 'reference run', notnull=True),
        Field('sender', 'reference device', notnull=True),
        Field('receiver', 'reference device', notnull=True),
        Field('received_us', type='bigint', notnull=True),
        Field('rssi', type='integer', notnull=True),
        Field('connectable', type='boolean', notnull=True),
        redefine=True,
        migrate=False
    )

    db.define_table(
        'position',
        Field('run', 'reference run', notnull=True),
        Field('device', 'reference device', notnull=True),
        Field('us', type='bigint', notnull=True),
        Field('pos_x', 'double', notnull=True),
        Field('pos_y', 'double', notnull=True),
        redefine=True,
        migrate=False
    )

    # TODO: Extra handling of summary vectors?


def reset_eval_tables(db, run=None):
    eval_tables = [
        'position',
        'advertisements',
        'bundle_transmission',
        'stored_bundle',
        'bundle',
        'conn_info',
        'device'  # last since every other reference this one
    ]

    if db._dbname == 'sqlite':
        for t in eval_tables:
            if run is not None:
                db(db[t].run == run).delete()
            else:
                db[t].drop()
    else:
        assert run is None
        for t in eval_tables:
            db(db[t]).delete()

    db.commit()
