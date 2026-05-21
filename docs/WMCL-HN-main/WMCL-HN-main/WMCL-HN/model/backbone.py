import torch
from torch import nn
from contextlib import contextmanager

# Define encoder network for MRI data
class EncoderMRI(nn.Module):
    def __init__(self, input_size):
        super(EncoderMRI, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(input_size, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 40),
        )

    def forward(self, x):
        return self.network(x)

# Define encoder network for PET data
class EncoderPET(nn.Module):
    def __init__(self, input_size):
        super(EncoderPET, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(input_size, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 40),
        )

    def forward(self, x):
        return self.network(x)

# Define encoder network for CSF data
class EncoderCSF(nn.Module):
    def __init__(self, input_size):
        super(EncoderCSF, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(input_size, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 40),
        )

    def forward(self, x):
        return self.network(x)

# A simple context manager that does nothing, useful for conditional contexts
@contextmanager
def null_context():
    yield

# Wrapper function for conditionally executing forward pass with a context
def model_forward_with_context(fn, args, freeze):
    encoding_context = null_context if not freeze else torch.no_grad
    with encoding_context():
        enc = fn(*args)
        if freeze:
            enc = enc.detach()
    return enc

# Backbone model that combines MRI, PET, and CSF encoders
class Backbone(nn.Module):
    def __init__(self):
        super().__init__()
        self.mri_mlp = EncoderMRI(input_size=90)
        self.pet_mlp = EncoderPET(input_size=90)
        self.csf_mlp = EncoderCSF(input_size=3)

    def forward(self, mri, pet, csf):

        enc_mri = model_forward_with_context(fn=self.mri_mlp, args=(mri,), freeze=False)
        enc_pet = model_forward_with_context(fn=self.pet_mlp, args=(pet,), freeze=False)
        enc_csf = model_forward_with_context(fn=self.csf_mlp, args=(csf,), freeze=False)

        return enc_mri, enc_pet, enc_csf
