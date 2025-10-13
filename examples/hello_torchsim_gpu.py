# /// script
# requires-python = "==3.12.*"
# dependencies = [
#     "torch-sim-atomistic",
#     "mace-torch>=0.3.12",
#     "pymatgen>=2025.2.18",
#     "ase>=3.23.1",
#     "certifi",
# ]
# ///
"""
NOTE: because this function returns an ase.Atoms object, the local environment
must have ase installed in order to deserialize the results (The local
environment does *not* need torch, torchsim, mace, etc).

Run this example like: $ uvx --from groundhog-hpc@latest --with ase hog run hello_torchsim_gpu.py
"""

import os

import groundhog_hpc as hog


@hog.function(
    # parameters for remote execution
    endpoint="5aafb4c1-27b2-40d8-a038-a0277611868f",  # anvil
    account="cis250461-gpu",
    qos="gpu",
    partition="gpu-debug",
    scheduler_options="#SBATCH --gpus-per-node=1",
)
def hello_torchsim(n_steps: int = 50):
    """we do a lil science around here"""
    import certifi
    import torch
    import torch_sim as ts
    from ase.build import bulk
    from mace.calculators.foundations_models import mace_mp
    from torch_sim.models.mace import MaceModel

    cu_atoms = bulk("Cu", "fcc", a=5.43, cubic=True)

    # Load the MACE "small" foundation model
    os.environ["SSL_CERT_FILE"] = certifi.where()
    mace = mace_mp(model="small", return_raw_model=True)
    mace_model = MaceModel(
        model=mace,
        device="cuda",
        dtype=torch.float64,
        compute_forces=True,
    )

    # Run the simulation with MACE
    final_state = ts.integrate(
        system=cu_atoms,
        model=mace_model,
        integrator=ts.nvt_langevin,
        n_steps=n_steps,
        temperature=2000,
        timestep=0.002,
    )

    final_atoms = final_state.to_atoms()
    return final_atoms


@hog.harness()
def main():
    """test the remote function"""
    import time

    future = hello_torchsim.submit()

    while not future.done():
        time.sleep(1)
        print(".", end="", flush=True)
    print("\n", flush=True)

    return future.result()
