import matplotlib.pyplot as plt 
import torch.nn as nn
from hw4dl.loaders.toy_loader import PolyData
import numpy as np 
from hw4dl.tools.manage_models import load_model, get_most_recent_model
from hw4dl.train import make_polyf, make_sigma_positive
from torch.utils.data import DataLoader
import torch
import os

def plot_network_performance(model:nn.Module,
                             toy_loader:PolyData,
                             device:str="cpu",
                             )->tuple[plt.Figure, plt.Axes, np.ndarray, np.ndarray]:
  """
  Plot ensemble performance on a toy dataset
  :param model: The model to plot
  :param toy_loader: The toy dataset
  :param device: The device to run the model on
  :return: A tuple of the figure, axes, x values, and epistemic variance
  """


  # set up the main plots 
  fig, ax = plt.subplots()
  ax.set_xlabel("X Values")
  ax.set_ylabel("Y Values")
  ax.set_xlim(toy_loader.lower, toy_loader.upper)
  # get samples we are evaluating at
  samples = np.linspace(toy_loader.lower, toy_loader.upper, 1000)
  # gt variance, plot true values
  var = toy_loader.varf(samples)
  ax.scatter(toy_loader.x, toy_loader.y, marker='.', alpha=0.1, label="Training Data")
  ax.plot(samples, toy_loader.polyf(samples), label="True Function")
  ax.fill_between(samples, toy_loader.polyf(samples) - var, toy_loader.polyf(samples) + var, alpha=0.5, label="True Variance")
  # get network predictions
  torch_input = torch.unsqueeze(torch.tensor(samples, dtype=torch.float32), 1).to(device)
  model.to(device)
  model.eval()
  model.scramble_batches = False
  outputs = model(torch_input)
  values = torch.stack(outputs).squeeze(-1)
  # plot network predictions
  for i in range(values.shape[0]):
    ax.plot(samples, values[i,:,0].detach().cpu().numpy(), alpha=0.5, label="_Network Prediction")
  # reduce to mean and variance
  means = values[:,:,0].mean(dim=0)
  sigma = make_sigma_positive(values[:,:,1]).mean(dim=0)
  epistemic_sigma = torch.std(values[:,:,0], dim=0)
  means = means.detach().cpu().numpy()
  sigma = sigma.detach().cpu().numpy()
  epistemic_sigma = epistemic_sigma.detach().cpu().numpy()
  # plot mean and variance and predicted epistemic variance
  ax.plot(samples, means, label="Mean Prediction")
  ax.fill_between(samples, means - np.square(sigma), means + np.square(sigma), alpha=0.5, label="Predicted Variance")
  ax.fill_between(samples, means - epistemic_sigma, means + epistemic_sigma, alpha=0.5, label="Epistemic Std")
  ax.legend()
  return fig, ax, samples, epistemic_sigma

def plot_cnn_performance(model, test_loader, savedir,device, split_id):
  """
  Plot the results of CNN training. Outputs a grid of five plots:
  1) A contour plot of the true mean function
  2) A contour plot of the true variance function
  3) A contour plot of the predicted function
  4) A contour plot of the predicted variance
  5) A contour plot of the epistemic variance
  :param model: A model of type VariableCNNBackbone
  :param test_loader: A dataloader of type Map2Loc.
  :param savedir: Directory to save the output plots
  :param device: "cuda" or "cpu"
  :param split_id: Index of the layer at which the model splits into inference heads (refer to split_idx in shared_cnn.py).
  :return: None
  """
  from matplotlib.patches import Rectangle

  testx, testy = np.meshgrid(np.arange(15), np.arange(15))
  x_input = (2 * testx.ravel()) / test_loader.shape[0] - 1
  y_input = (2 * testy.ravel()) / test_loader.shape[0] - 1
  gt_mean = test_loader.polyf(x_input, y_input)
  gt_var = test_loader.varf(x_input, y_input)

  # fig, axes = plt.subplots(nrows=2, ncols=3, figsize=(5,5))
  # fig.tight_layout()
  plt.figure(figsize=(9, 6))
  ax1 = plt.subplot(231)
  ax2 = plt.subplot(233)
  ax3 = plt.subplot(234)
  ax4 = plt.subplot(235)
  ax5 = plt.subplot(236)
  # plt.tight_layout()
  plt.subplots_adjust(hspace=0.3, wspace=0.3)

  axes = [ax1, ax2, ax3, ax4, ax5]
  # axes = axes.flatten()
  axes[0].imshow(gt_mean.reshape((15, 15)))
  axes[0].set_title("True function")
  axes[1].imshow(gt_var.reshape((15, 15)))
  axes[1].set_title("True variance")

  all_inputs = []
  for x, y in zip(testx.ravel(), testy.ravel()):
    inputs = np.zeros((15, 15))
    inputs[x, y] = 1
    all_inputs.append(torch.tensor(inputs))
  inputs = torch.stack(all_inputs).unsqueeze(1).type(torch.float32).to(device)
  outputs = model(inputs)
  values = torch.stack(outputs).squeeze(-1)
  means = values[:, :, 0].mean(dim=0)
  means_arr = means.detach().cpu().numpy()
  axes[2].imshow(means_arr.reshape((15, 15)))
  axes[2].set_title("Predicted function")

  sigma = torch.sqrt(
    torch.mean(make_sigma_positive(values[:, :, 1]) + torch.square(values[:, :, 0]), dim=0) - torch.square(means))
  sigma = sigma.detach().cpu().numpy()
  epistemic_sigma = torch.std(values[:, :, 0], dim=0)
  epistemic_sigma = epistemic_sigma.detach().cpu().numpy()

  axes[3].imshow(np.square(sigma).reshape((15, 15)))
  axes[3].set_title("Predicted variance")

  axes[4].imshow(np.square(epistemic_sigma).reshape((15, 15)))
  axes[4].set_title("Epistemic variance")
  for gap in test_loader.gaps:
    for i in range(4):
      width = gap[1] - gap[0]
      height = gap[3] - gap[2]
      x1, y1 = gap[0], gap[2]
      rect = Rectangle((x1, y1), width, height, linewidth=2, edgecolor='red', facecolor='none')
      axes[i].add_patch(rect)
  plt.savefig(os.path.join(savedir, f"result_plot_split_{split_id}.png"))
  plt.savefig(os.path.join(savedir, f"result_plot_split_{split_id}.png"))

if __name__ == "__main__":

  most_recent_model = get_most_recent_model()
  model, config = load_model(most_recent_model)
  polyf, varf, gaps = make_polyf(config["polyf_type"])
  train_dataset = PolyData(polyf, varf, gaps, size=config["train_size"], seed=1111)
  # val_dataset = PolyData(polyf, varf, gaps, size=args.val_size, seed=2222)
  # test_dataset = PolyData(polyf, varf, gaps, size=args.test_size, seed=3333)

  fig, ax = plot_network_performance(model, train_dataset)
  plt.show()