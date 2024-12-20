import torch
import torch.nn as nn
import torch.nn.functional as F


def BCEDiceLoss(input, target):
    bce = F.binary_cross_entropy_with_logits(input, target)
    smooth = 1e-5
    input = torch.sigmoid(input)
    num = target.size(0)
    input = input.view(num, -1)
    target = target.view(num, -1)
    intersection = (input * target)
    dice = (2. * intersection.sum(1) + smooth) / (input.sum(1) + target.sum(1) + smooth)
    dice = 1 - dice.sum() / num
    return 0.5 * bce + dice


def build_target(target: torch.Tensor, num_classes: int = 2, ignore_index: int = -100):
    """build target for dice coefficient"""
    dice_target = target.clone()
    if ignore_index >= 0:
        ignore_mask = torch.eq(target, ignore_index)
        dice_target[ignore_mask] = 0
        # [N, H, W] -> [N, H, W, C]
        dice_target = nn.functional.one_hot(dice_target, num_classes).float()
        dice_target[ignore_mask] = ignore_index
    else:
        dice_target = nn.functional.one_hot(dice_target, num_classes).float()

    return dice_target.permute(0, 3, 1, 2)


def dice_coeff(x: torch.Tensor, target: torch.Tensor, ignore_index: int = -100, epsilon=1e-6):

    d = 0.
    batch_size = x.shape[0]
    for i in range(batch_size):
        x_i = x[i].reshape(-1)
        t_i = target[i].reshape(-1)
        if ignore_index >= 0:
            # 找出mask中不为ignore_index的区域
            roi_mask = torch.ne(t_i, ignore_index)
            x_i = x_i[roi_mask]
            t_i = t_i[roi_mask]
        inter = torch.dot(x_i, t_i)
        sets_sum = torch.sum(x_i) + torch.sum(t_i)
        if sets_sum == 0:
            sets_sum = 2 * inter

        d += (2 * inter + epsilon) / (sets_sum + epsilon)

    return d / batch_size


def multiclass_dice_coeff(x: torch.Tensor, target: torch.Tensor, ignore_index: int = -100, epsilon=1e-6):
    """Average of Dice coefficient for all classes"""
    dice = 0.
    for channel in range(x.shape[1]):
        dice += dice_coeff(x[:, channel, ...], target[:, channel, ...], ignore_index, epsilon)

    return dice / x.shape[1]


def dice_loss(x: torch.Tensor, target: torch.Tensor, multiclass: bool = False, ignore_index: int = -100):
    # Dice loss (objective to minimize) between 0 and 1
    x = nn.functional.softmax(x, dim=1)
    fn = multiclass_dice_coeff if multiclass else dice_coeff
    return 1 - fn(x, target, ignore_index=ignore_index)

def TwerkyLoss(input, target, alpha=0.5, beta=0.5, smooth=1e-5):
    """
    Twerky loss combines a custom formulation of binary cross-entropy with 
    a modified Dice coefficient for enhanced segmentation accuracy.
    
    Parameters:
        input (torch.Tensor): Predicted tensor of logits.
        target (torch.Tensor): Ground truth tensor.
        alpha (float): Weight for the BCE component.
        beta (float): Weight for the Dice component.
        smooth (float): Smoothing constant to prevent division by zero.
    
    Returns:
        torch.Tensor: Computed Twerky loss.
    """
    # Binary Cross-Entropy part
    bce = F.binary_cross_entropy_with_logits(input, target)

    # Dice component
    input = torch.sigmoid(input)
    intersection = (input * target).sum(dim=(2, 3))
    dice = (2. * intersection + smooth) / (input.sum(dim=(2, 3)) + target.sum(dim=(2, 3)) + smooth)
    dice_loss = 1 - dice.mean(dim=1)

    # Twerky Loss as a weighted sum of BCE and Dice components
    twerky_loss = alpha * bce + beta * dice_loss.mean()

    return twerky_loss
