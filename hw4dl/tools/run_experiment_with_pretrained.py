from collections import namedtuple
import os, torch
import numpy as np 
import datetime 
from hw4dl import ROOT_DIR
from hw4dl.main import parse_options
from hw4dl.train import train, make_polyf
from hw4dl.loaders.toy_loader import PolyData
from hw4dl.tools.manage_models import load_model
from hw4dl.tools.score_ensemble import score_network_performance
from hw4dl.tools.plot_ensemble_results import plot_network_performance
import json
import pandas as pd 
import matplotlib.pyplot as plt 

ExpConfig = namedtuple("exp_config", 
                        ["name",
                         "split_indexes",
                         "seed", 
                         "device",
                        ])

def set_all_seeds(seed):
  # this one doesn't deserve a docstring
  torch.manual_seed(seed)
  if torch.cuda.is_available():
    torch.cuda.manual_seed_all(seed)
  np.random.seed(seed)

def run_experiment(exp_config:ExpConfig):
  """
  Run an experiment with a pretrained model!
  :param exp_config: The experiment configuration

  Same as run_fc_experiment except uses the models that are already trained
  Overwrite the csv file and the plots 
  """
  # exp_name = exp_config.name + "_" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
  base_path = os.path.join(ROOT_DIR, "experiments")
  # get most recent experiment directory
  dirs = [os.path.join(base_path, d) for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
  dirs.sort(key=lambda x: os.path.getmtime(x))
  base_exp_path = dirs[-1]

  # output results structure
  results = dict(split_idx=[], mean_mse=[], sigma_mse=[], per_correct=[], epi_score=[], shared_parameters=[], total_parameters=[])

  epistemic_sigmas = []
  samples = None

  # fix the seeds
  set_all_seeds(exp_config.seed)
  # for each split index
  for split_idx in exp_config.split_indexes:

    args = parse_options()
    args.split_idx = split_idx
    args.device_type = exp_config.device
    args.scrambe_batches = True
    split_idx_dir= os.path.join(base_exp_path, f"split_{split_idx}")


    model_filename = None 
    for file in os.listdir(split_idx_dir):
      if file.endswith(".pt"):
        model_filename = os.path.basename(file)[:-3]
    model, config = load_model(os.path.join(split_idx_dir, model_filename))
    # print number of shared and split layers
    shared_parameters = np.sum([np.prod(p.shape) for p in model.shared_backbone.parameters()])
    split_parameters = np.sum([np.prod(p.shape) for p in model.heads.parameters()])
    results["shared_parameters"].append(shared_parameters)
    results["total_parameters"].append(split_parameters + shared_parameters)

    # evaluate network performance

    polyf, varf, gaps = make_polyf(config["polyf_type"])
    train_dataset = PolyData(polyf, varf, gaps, size=config["train_size"], seed=1111)
    mean_mse, sigma_mse, per_correct, epi_score = score_network_performance(model, train_dataset, 0.1)
    results["split_idx"].append(split_idx)
    results["mean_mse"].append(mean_mse)
    results["sigma_mse"].append(sigma_mse)
    results["per_correct"].append(per_correct)
    results["epi_score"].append(epi_score)
    # print out performance 

    # # create plot
    fig, ax, samples, epistemic_values = plot_network_performance(model, train_dataset)
    samples = samples
    epistemic_sigmas.append(epistemic_values)
    fig.savefig(os.path.join(base_exp_path, f"{split_idx:03d}_performance.png"))

    # save results
    results_df = pd.DataFrame(results)
    # print(results_df)
    results_df.to_csv(os.path.join(base_exp_path, "results.csv"), index=False)

  # create an epistemic sigma plot 
  fig, ax = plt.subplots()
  ax.set_xlim(train_dataset.lower, train_dataset.upper)
  for epi_values, split_idx in zip(epistemic_sigmas, exp_config.split_indexes):
    ax.plot(samples, epi_values, label=f"Split {split_idx}")
  ax.set_ylabel("Epistemic Std")
  ax.set_xlabel("X Value")
  ax.axvspan(-1, -0.5, alpha=0.1, color='green')
  ax.axvspan(0.5, 1, alpha=0.1, color='green')
  ax.axvspan(-0.5, 0.5, alpha=0.1, color='red')
  ax.legend()
  fig.savefig(os.path.join(base_exp_path, "epistemic_sigma.png"))


if __name__ == "__main__":
  import argparse
  parser = argparse.ArgumentParser()
  parser.add_argument("--name", type=str, default="fc_experiment")
  parser.add_argument("--split_indexes", type=int, nargs="+", default=[0, 1, 2, 3, 4, 5])
  parser.add_argument("--seed", type=int, default=1111)
  parser.add_argument("--device_type", type=str, default="cpu")
  args = parser.parse_args()
  exp_config = ExpConfig(name=args.name, split_indexes=args.split_indexes, seed=args.seed, device=args.device_type)
  run_experiment(exp_config)
