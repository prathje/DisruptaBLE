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
        Field('run', 'reference run'),
        Field('device',  type='integer', notnull=True),
        Field('us',  type='bigint', notnull=True),
        Field('data_json',  type='text', notnull=True),
        redefine=False
    )
