import torch
import torch.nn as nn

class VariableBackbone(nn.Module):
  def __init__(self, layer_shapes:tuple, split_idx:int, num_heads:int):
    """
    Create a NN with variable amount of shared backbone 

    @param layer_shapes: tuple of layer shapes eg. (input, hidden1, hidden2, output) 
    @param split_idx: index of layer to split the backbone. Eg 2 would split after hidden2
    @param num_heads: number of heads to create

    """
    super().__init__()
    self.layer_shapes = layer_shapes
    self.split_idx = split_idx
    self.num_heads = num_heads
    assert self.split_idx < len(self.layer_shapes)-1, "Split index must be less than the number of layers"
    shared_backbone = []
    for i in range(self.split_idx):
      shared_backbone.append(nn.Linear(layer_shapes[i], layer_shapes[i+1]))
                             
      if i != len(self.layer_shapes)-2:
        shared_backbone.append(nn.ReLU())
    self.shared_backbone = nn.Sequential(*shared_backbone)

    heads = []
    for i in range(self.num_heads):
      head_i = []
      for j in range(self.split_idx, len(self.layer_shapes)-1):
        head_i.append(nn.Linear(layer_shapes[j], layer_shapes[j+1]))
        if j != len(self.layer_shapes)-2:
          head_i.append(nn.ReLU())
      heads.append(nn.Sequential(*head_i))
    self.heads = nn.ModuleList(heads)

  def forward(self, x):
    x = self.shared_backbone(x)
    outputs = []
    for head in self.heads:
      outputs.append(head(x))
    return outputs

if __name__ == "__main__":
  layer_shapes = [10, 20, 30, 40]
  split_idx = 2
  num_heads = 3
  model = VariableBackbone(layer_shapes, split_idx, num_heads)
  print(model) 