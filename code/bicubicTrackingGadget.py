import time
import logging

import torch
import numpy as np

import ismrmrd
import gadgetron

from modules.schemas.bicubic_sr import (
    BicubicModel,
    BicubicPretransformations,
    BicubicPosttransformations,
)

from modules.schemas.mlc_tracking import (
    MLCImageArrayParser,
    MLCSocketmaker,
    MLCStructmaker,
)


def main(connection):
    logging.basicConfig(level=logging.DEBUG)

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    logging.debug(f"Device used for inference: {device}")

    model = BicubicModel(device, "64_to_256_bicubic_interpolation_JIT.pt")

    with MLCSocketmaker() as MLCsm:
        MLCsm.create_socketclient()
        MLCsm.connect_socketclient()

        for acquisition in connection:
            data = acquisition.data

            data_cp = np.copy(data)

            pretransformation_class = BicubicPretransformations(data_cp, device)

            image = pretransformation_class.pretransform()

            image_inferred = model.perform_inference(image)

            posttransformation_class = BicubicPosttransformations(image_inferred)

            image_inferred = posttransformation_class.posttransform()

            parser_class = MLCImageArrayParser(acquisition, connection)

            acquisition_data = parser_class.retrieve_acquisition_data()

            connection_data = parser_class.retrieve_connection_data()

            structmaker_class = MLCStructmaker(
                acquisition_data, connection_data, image_inferred, upsample_ratio=4
            )

            packed_struct = structmaker_class.pack_struct()

            logging.info(f"{structmaker_class.header}")

            MLCsm.send_packed_struct(packed_struct)

            image_to_send = ismrmrd.image.Image.from_array(
                image_inferred, image_type=ismrmrd.IMTYPE_MAGNITUDE, transpose=True
            )

            connection.send(image_to_send)
