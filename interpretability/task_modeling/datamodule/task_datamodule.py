import logging
import os

import dotenv
import h5py
import numpy as np
import pytorch_lightning as pl
import torch
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, TensorDataset
from gymnasium import Env

import interpretability.task_modeling.task_envs.task_envs as task_envs

logger = logging.getLogger(__name__)

# Load the project data home
dotenv.load_dotenv(override=True)
DATA_HOME = os.environ["TASK_TRAINED_DATA_HOME"]


def to_tensor(array):
    return torch.tensor(array, dtype=torch.float)


class TaskDataModule(pl.LightningDataModule):
    def __init__(
        self,
        task_env: Env = None,
        n_samples: int = 2000,
        n_timesteps: int = 200,
        seed: int = 0,
        noise: float = 0,
        batch_size: int = 64,
        num_workers: int = 4,
        task_params: dict = None,
    ):
        super().__init__()
        self.save_hyperparameters()
        # Generate the dataset tag
        self.task_env = task_env
        self.noise = noise
        self.name = (
            f"{task_env.dataset_name}_{n_samples}S_{task_env.n_timesteps}T"
            f"_{seed}seed_{self.noise}"
        )
        # Append the task_params to the name
        if task_params is not None:
            for key, val in task_params.items():
                self.name += f"_{key}_{val}"

        self.input_labels = self.task_env.input_labels
        self.output_labels = self.task_env.output_labels

    def prepare_data(self):
        hps = self.hparams

        filename = f"{self.name}.h5"
        fpath = os.path.join(DATA_HOME, filename)
        if os.path.isfile(fpath):
            logger.info(f"Loading dataset {self.name}")
            return
        logger.info(f"Generating dataset {self.name}")
        # Simulate the task
        outputs_ds, inputs_ds, comb_ds = self.task_env.generate_dataset()
        # Standardize and record original mean and standard deviations
                # Perform data splits
        inds = np.arange(hps.n_samples)
        train_inds, test_inds = train_test_split(
            inds, test_size=0.2, random_state=hps.seed
        )
        train_inds, valid_inds = train_test_split(
            train_inds, test_size=0.2, random_state=hps.seed
        )
        # Save the trajectories
        with h5py.File(fpath, "w") as h5file:
            h5file.create_dataset("train_data", data = comb_ds[train_inds])
            h5file.create_dataset("valid_data", data = comb_ds[valid_inds])
            h5file.create_dataset("test_data", data = comb_ds[test_inds])
            
            h5file.create_dataset("train_outputs", data = outputs_ds[train_inds])
            h5file.create_dataset("valid_outputs", data = outputs_ds[valid_inds])
            h5file.create_dataset("test_outputs", data = outputs_ds[test_inds])
            
            h5file.create_dataset("train_inputs", data = inputs_ds[train_inds])
            h5file.create_dataset("valid_inputs", data = inputs_ds[valid_inds])
            h5file.create_dataset("test_inputs", data = inputs_ds[test_inds])
            
            h5file.create_dataset("train_inds", data = train_inds)
            h5file.create_dataset("valid_inds", data = valid_inds)
            h5file.create_dataset("test_inds", data = test_inds)

    def setup(self, stage=None):
        # Load data arrays from file
        data_path = os.path.join(DATA_HOME, f"{self.name}.h5")
        with h5py.File(data_path, "r") as h5file:
            # Load the data
            train_comb = to_tensor(h5file["train_data"][()])
            valid_comb = to_tensor(h5file["valid_data"][()])
            test_comb = to_tensor(h5file["test_data"][()])
           
            train_outputs = to_tensor(h5file["train_outputs"][()])
            valid_outputs = to_tensor(h5file["valid_outputs"][()])
            test_outputs = to_tensor(h5file["test_outputs"][()])
           
            train_inputs = to_tensor(h5file["train_inputs"][()])
            valid_inputs = to_tensor(h5file["valid_inputs"][()])
            test_inputs = to_tensor(h5file["test_inputs"][()])
           
            # Load the indices
            train_inds = to_tensor(h5file["train_inds"][()])
            valid_inds = to_tensor(h5file["valid_inds"][()])
            test_inds = to_tensor(h5file["test_inds"][()])

        # Store datasets
        self.train_ds = TensorDataset(
            train_outputs, train_inputs, train_comb, train_inds
        )
        self.valid_ds = TensorDataset(
            valid_outputs, valid_inputs, valid_comb, valid_inds
        )
        self.test_ds = TensorDataset(test_outputs, test_inputs, test_comb, test_inds)

    def train_dataloader(self, shuffle=True):
        train_dl = DataLoader(
            self.train_ds,
            batch_size=self.hparams.batch_size,
            num_workers=self.hparams.num_workers,
            shuffle=shuffle,
        )
        return train_dl

    def val_dataloader(self):
        valid_dl = DataLoader(
            self.valid_ds,
            batch_size=self.hparams.batch_size,
            num_workers=self.hparams.num_workers,
        )
        return valid_dl