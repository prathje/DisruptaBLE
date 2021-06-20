import dotenv
import os
import numpy

config = {
    **dotenv.dotenv_values(".env"),  # load shared development variables
    **dotenv.dotenv_values(".env.local"),  # load sensitive variables
    **os.environ,  # override loaded values with environment variables
}

MODEL_SECONDS_PER_STEP = float(config['BF_SIM_MODEL_SECONDS_PER_STEP'])
MODEL_STEPS_PER_SECOND = 1.0/MODEL_SECONDS_PER_STEP

MODEL_US_PER_STEP = int(MODEL_SECONDS_PER_STEP * 1000000.0)
MAX_US = int(float(config['BF_SIM_LENGTH']) * 1000000.0)

NUM_NODES = int(config['BF_SIM_NUM_NODES'])








if __name__ == "__main__":
    numpy.random.seed(42)

