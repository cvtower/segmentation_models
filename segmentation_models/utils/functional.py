from keras_applications import get_submodules_from_kwargs
from . import inject_global_submodules

# from keras.utils.generic_utils import get_custom_objects

__all__ = [
    'iou_score', 'jaccard_score', 'f1_score', 'f2_score', 'dice_score',
    'get_f_score', 'get_iou_score', 'get_jaccard_score',
]

SMOOTH = 1.


def iou_score(gt, pr, class_weights=1., smooth=SMOOTH, per_image=True, threshold=None, **kwargs):
    r""" The `Jaccard index`_, also known as Intersection over Union and the Jaccard similarity coefficient
    (originally coined coefficient de communauté by Paul Jaccard), is a statistic used for comparing the
    similarity and diversity of sample sets. The Jaccard coefficient measures similarity between finite sample sets,
    and is defined as the size of the intersection divided by the size of the union of the sample sets:

    .. math:: J(A, B) = \frac{A \cap B}{A \cup B}

    Args:
        gt: ground truth 4D keras tensor (B, H, W, C)
        pr: prediction 4D keras tensor (B, H, W, C)
        class_weights: 1. or list of class weights, len(weights) = C
        smooth: value to avoid division by zero
        per_image: if ``True``, metric is calculated as mean over images in batch (B),
            else over whole batch
        threshold: value to round predictions (use ``>`` comparison), if ``None`` prediction will not be round

    Returns:
        IoU/Jaccard score in range [0, 1]

    .. _`Jaccard index`: https://en.wikipedia.org/wiki/Jaccard_index

    """

    backend = get_submodules_from_kwargs(kwargs)[0]

    if per_image:
        axes = [1, 2]
    else:
        axes = [0, 1, 2]

    if threshold is not None:
        pr = backend.greater(pr, threshold)
        pr = backend.cast(pr, backend.floatx())

    intersection = backend.sum(gt * pr, axis=axes)
    union = backend.sum(gt + pr, axis=axes) - intersection
    iou = (intersection + smooth) / (union + smooth)

    # mean per image
    if per_image:
        iou = backend.mean(iou, axis=0)

    # weighted mean per class
    iou = backend.mean(iou * class_weights)

    return iou


def f_score(gt, pr, class_weights=1, beta=1, smooth=SMOOTH, per_image=True, threshold=None, **kwargs):
    r"""The F-score (Dice coefficient) can be interpreted as a weighted average of the precision and recall,
    where an F-score reaches its best value at 1 and worst score at 0.
    The relative contribution of ``precision`` and ``recall`` to the F1-score are equal.
    The formula for the F score is:

    .. math:: F_\beta(precision, recall) = (1 + \beta^2) \frac{precision \cdot recall}
        {\beta^2 \cdot precision + recall}

    The formula in terms of *Type I* and *Type II* errors:

    .. math:: F_\beta(A, B) = \frac{(1 + \beta^2) TP} {(1 + \beta^2) TP + \beta^2 FN + FP}


    where:
        TP - true positive;
        FP - false positive;
        FN - false negative;

    Args:
        gt: ground truth 4D keras tensor (B, H, W, C)
        pr: prediction 4D keras tensor (B, H, W, C)
        class_weights: 1. or list of class weights, len(weights) = C
        beta: f-score coefficient
        smooth: value to avoid division by zero
        per_image: if ``True``, metric is calculated as mean over images in batch (B),
            else over whole batch
        threshold: value to round predictions (use ``>`` comparison), if ``None`` prediction will not be round

    Returns:
        F-score in range [0, 1]

    """

    backend = get_submodules_from_kwargs(kwargs)[0]

    if per_image:
        axes = [1, 2]
    else:
        axes = [0, 1, 2]

    if threshold is not None:
        pr = backend.greater(pr, threshold)
        pr = backend.cast(pr, backend.floatx())

    tp = backend.sum(gt * pr, axis=axes)
    fp = backend.sum(pr, axis=axes) - tp
    fn = backend.sum(gt, axis=axes) - tp

    score = ((1 + beta ** 2) * tp + smooth) \
            / ((1 + beta ** 2) * tp + beta ** 2 * fn + fp + smooth)

    # mean per image
    if per_image:
        score = backend.mean(score, axis=0)

    # weighted mean per class
    score = backend.mean(score * class_weights)

    return score


def categorical_crossentropy(gt, pr, class_weights=1., **kwargs):
    backend = kwargs['backend']

    # scale predictions so that the class probas of each sample sum to 1
    axis = 3 if backend.image_data_format() == 'channels_last' else 1
    pr /= backend.sum(pr, axis=axis, keepdims=True)

    # clip to prevent NaN's and Inf's
    pr = backend.clip(pr, backend.epsilon(), 1 - backend.epsilon())

    # calculate loss
    output = gt * backend.log(pr) * class_weights
    return - backend.mean(output)


def bianary_crossentropy(gt, pr, **kwargs):
    backend = kwargs['backend']
    return backend.mean(backend.binary_crossentropy(gt, pr))


def categorical_focal_loss(gt, pr, gamma=2.0, alpha=0.25, **kwargs):
    """Implementation of Focal Loss from the paper in multiclass classification
    Formula:
        loss = -alpha*((1-p)^gamma)*log(p)
    Arguments:
        alpha: the same as weighting factor in balanced cross entropy, default 0.25
        gamma: focusing parameter for modulating factor (1-p), default 2.0
    """

    backend = kwargs['backend']

    # clip to prevent NaN's and Inf's
    pr = backend.clip(pr, backend.epsilon(), 1.0 - backend.epsilon())

    # Calculate cross entropy
    cross_entropy = - gt * backend.log(pr)

    # Calculate weight that consists of  modulating factor and weighting factor
    weight = alpha * gt * backend.pow((1 - pr), gamma)

    # Calculate focal loss
    loss = weight * cross_entropy

    return backend.mean(loss)


def focal_loss(gt, pr, gamma=2.0, alpha=0.25, **kwargs):
    """Implementation of Focal Loss from the paper in multiclass classification

    Parameters:
        alpha -- the same as wighting factor in balanced cross entropy
        gamma -- focusing parameter for modulating factor (1-p)
    Default value:
        gamma -- 2.0 as mentioned in the paper
        alpha -- 0.25 as mentioned in the paper
    """
    l1 = categorical_focal_loss(gt, pr, gamma=gamma, alpha=alpha, **kwargs)
    l2 = categorical_focal_loss((1 - gt), (1 - pr), gamma=gamma, alpha=alpha, **kwargs)
    return l1 + l2