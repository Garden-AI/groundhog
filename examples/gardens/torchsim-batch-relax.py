# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "ase",
#     "torch",
#     "torch-geometric",
#     "cuequivariance",
#     "cuequivariance-torch",
#     "cuequivariance-ops-torch-cu12",
#     "torch-sim-atomistic",
#     "pymatgen",
#     "dgl",
#     "sevenn",
# ]
# ///

import groundhog_hpc as hog

EDITH = "a01b9350-e57d-4c8e-ad95-b4cb3c4cd1bb"
ANVIL = "5aafb4c1-27b2-40d8-a038-a0277611868f"

edith_init = """true;
module load openmpi;
export PATH=/usr/mpi/gcc/openmpi-4.1.7rc1/bin:$PATH;
export PATH=$PATH:/usr/sbin;
"""

anvil_init = """
export CFLAGS=$(echo $CFLAGS | sed 's/-fdebug-default-version=4//g')
export CXXFLAGS=$(echo $CXXFLAGS | sed 's/-fdebug-default-version=4//g')
"""


@hog.function(
    endpoint=ANVIL,
    account="cis250461-gpu",
    qos="gpu",
    partition="gpu-debug",
    worker_init=anvil_init,
    scheduler_options="#SBATCH --gpus-per-node=1",
)
def batch_relax(
    xyz_contents,
    model: str = "sevennet",
    relaxation_options=None,
    dtype_str: str = "float64",
) -> str:
    """
    Standalone batch relaxation function that processes structures in small batches.

    This function is designed to be executed on remote HPC systems via globus-compute
    executors, independent of the MLIPGarden class. All imports and helper functions
    are contained within this function for remote execution compatibility.

    Args:
        xyz_file_path: Path to XYZ file containing structures
        model: Model to use for relaxation (any torch-sim supported model)
        max_batch_size: Maximum structures per batch (used as fallback)
        relaxation_options: Additional options passed through to the relaxation function
        dtype_str: Data type string ('float64' or 'float32')

    Returns:
        String content of the results XYZ file
    """
    # All imports must be inside the function for remote execution
    import os
    import uuid
    from io import StringIO
    from pathlib import Path

    # Fix NUMEXPR threading issue early
    os.environ["NUMEXPR_MAX_THREADS"] = "256"

    import torch
    import torch_sim as ts
    from ase.io import read, write
    from torch_sim import optimizers

    def load_torch_sim_model(model_name: str, device: str = "cpu", dtype=None):
        """Load a torch-sim model by name."""
        if dtype is None:
            dtype = torch.float32
        print(f"🔧 Loading {model_name} model on {device}...")
        if model_name in ["soft-sphere", "lennard-jones", "morse"]:
            if model_name == "soft-sphere":
                from torch_sim.models.soft_sphere import SoftSphereModel

                return SoftSphereModel(device=device, dtype=dtype)
            elif model_name == "lennard-jones":
                from torch_sim.models.lennard_jones import LennardJonesModel

                return LennardJonesModel(
                    sigma=2.0, epsilon=0.1, device=device, dtype=dtype
                )
            elif model_name == "morse":
                from torch_sim.models.morse import MorseModel

                return MorseModel(device=device, dtype=dtype)
        elif model_name == "sevennet":
            from sevenn.calculator import SevenNetCalculator
            from torch_sim.models.sevennet import SevenNetModel

            modal = "mpa"
            sevennet_calculator = SevenNetCalculator(
                model="7net-mf-ompa", modal=modal, device=device
            )

            return SevenNetModel(
                model=sevennet_calculator.model, modal=modal, device=device
            )
        else:
            raise ValueError(f"Unknown model: {model_name}")

    xyz_path = Path("test_structures.xyz")

    if relaxation_options is None:
        relaxation_options = {}

    max_steps = relaxation_options.get("max_steps", 500)
    # fmax = relaxation_options.get("fmax", 0.05)

    # Parse xyz content using StringIO
    string_file = StringIO(xyz_contents)
    all_atoms = read(string_file, index=":", format="extxyz")
    num_structures = len(all_atoms)

    # Create results file path
    suffix = "relaxed"
    results_filename = f"{xyz_path.stem}_{suffix}_{uuid.uuid4().hex[:8]}.xyz"
    results_path = xyz_path.parent / results_filename

    print(f"📝 Results will be saved to: {results_path}")
    print(f"🚀 Starting batch relaxation of {num_structures} structures...")

    # Set up device and resolve dtype
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if dtype_str == "float64":
        torch_dtype = torch.float64
    elif dtype_str == "float32":
        torch_dtype = torch.float32
    else:
        raise ValueError(f"Unsupported dtype string: {dtype_str}")

    torch_sim_model = load_torch_sim_model(model, device, torch_dtype)

    # Extract material IDs (create if not present) and atom counts
    mat_ids = []
    for idx, atoms in enumerate(all_atoms):
        if "material_id" in atoms.info:
            mat_ids.append(atoms.info["material_id"])
        else:
            mat_id = f"material_{idx}"
            atoms.info["material_id"] = mat_id
            mat_ids.append(mat_id)

    atom_counts = [len(atoms) for atoms in all_atoms]

    print(f"  - Found {len(all_atoms)} materials")
    print(f"  - Atom count range: {min(atom_counts)} - {max(atom_counts)}")

    # Create lists for each size category with (index, atoms, mat_id) tuples
    small_materials = []  # <10 atoms
    medium_materials = []  # 10-19 atoms
    large_materials = []  # 20+ atoms

    for idx, (atoms, mat_id, n_atoms) in enumerate(
        zip(all_atoms, mat_ids, atom_counts)
    ):
        material_data = (idx, atoms, mat_id)
        if n_atoms < 10:
            small_materials.append(material_data)
        elif n_atoms < 20:
            medium_materials.append(material_data)
        else:
            large_materials.append(material_data)

    print("\n📊 Size distribution:")
    print(f"  - Small (<10 atoms): {len(small_materials)} materials")
    print(f"  - Medium (10-19 atoms): {len(medium_materials)} materials")
    print(f"  - Large (20+ atoms): {len(large_materials)} materials")

    # Define batch sizes for each category
    batch_sizes = {"small": 200, "medium": 100, "large": 5}

    # Track results for proper ordering
    all_results = []
    has_written = False

    def process_category(materials, category_name, batch_size):
        """Process all materials in a size category."""
        nonlocal has_written

        if not materials:
            print("nothing in " + category_name)
            return

        n_batches = (len(materials) + batch_size - 1) // batch_size
        print(
            f"\n🔄 Processing {category_name} materials: {len(materials)} materials in {n_batches} batches"
        )

        for batch_idx in range(n_batches):
            start_idx = batch_idx * batch_size
            end_idx = min((batch_idx + 1) * batch_size, len(materials))
            batch_materials = materials[start_idx:end_idx]

            batch_atoms = [item[1] for item in batch_materials]
            batch_mat_ids = [item[2] for item in batch_materials]
            batch_original_indices = [item[0] for item in batch_materials]

            print(
                f"  - Batch {batch_idx + 1}/{n_batches}: {len(batch_atoms)} materials"
            )

            # Initialize state
            initial_state = ts.initialize_state(
                batch_atoms, device=device, dtype=torch_dtype
            )

            optimizer = optimizers.OPTIM_REGISTRY["fire"]

            result_state = ts.optimize(
                system=initial_state,
                model=torch_sim_model,
                optimizer=optimizer,
                max_steps=max_steps,
            )

            result_atoms_list = result_state.to_atoms()
            energies_tensor = result_state.energy

            # Ensure energies are always in a list
            if energies_tensor.dim() == 0:
                # This is a 0-d tensor, so convert to a list with one item
                final_energies = [energies_tensor.item()]
            else:
                # This is a 1-d or higher tensor, tolist() works correctly
                final_energies = energies_tensor.cpu().tolist()

            # Also ensure the atoms list is always a list for consistency
            if not isinstance(result_atoms_list, list):
                result_atoms_list = [result_atoms_list]

            batch_results = [
                {
                    "material_id": mat_id,
                    "final_energy": energy,
                    "relaxed_atoms": atoms,
                    "original_index": orig_idx,
                }
                for mat_id, atoms, energy, orig_idx in zip(
                    batch_mat_ids,
                    result_atoms_list,
                    final_energies,
                    batch_original_indices,
                )
            ]
            all_results.extend(batch_results)

            # Write results incrementally in case job gets killed before it finishes
            print(f"💾 Saving {len(result_atoms_list)} structures to {results_path}...")
            for atoms, energy, mat_id in zip(
                result_atoms_list, final_energies, batch_mat_ids
            ):
                atoms.info["energy"] = energy
                atoms.info["final_energy"] = energy
                atoms.info["material_id"] = mat_id
                atoms.info["model"] = model
                atoms.info["relaxed"] = True
                write(results_path, atoms, append=has_written)
                if not has_written:
                    has_written = True

    # Process each category
    process_category(small_materials, "small", batch_sizes["small"])
    process_category(medium_materials, "medium", batch_sizes["medium"])
    process_category(large_materials, "large", batch_sizes["large"])

    # Read final results content
    with open(results_path, "r") as f:
        results_content = f.read()

    print(
        f"\n✅ Relaxation complete! Returning results for {num_structures} structures"
    )
    return results_content


@hog.harness()
def main():
    with open("./test_structures.xyz", "r") as f:
        xyz_content = f.read()
    contents = batch_relax.remote(xyz_content, model="sevennet")
    print(contents)
