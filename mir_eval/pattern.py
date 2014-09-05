"""Functions for evaluating the task of pattern discovery.

Input Format
============

The input format can be automatically generated by calling the function
load_patterns from the io module using a text file with the MIREX
form at as input. Here is a description of the input format:

List of list of tuples:
    Patterns: First level list
    Occurrences: Second level list
    Onset_Midi: Tuple of (onset_time, mid_note)

A pattern is a list of occurrences. The first occurrence must be the prototype
of that pattern (i.e. the most representative of all the occurrences).

An occurrence is a list of tuples containing the onset time and the midi
note number.

Metrics implemented
===================

Standard Precision, Recall and F1 Score
---------------------------------------

Strict metric in order to find the possibly transposed patterns of exact
length. This is the only metric that considers transposed patterns.
Used and described here:

Tom Collins, Jeremy Thurlow, Robin Laney, Alistair Willis, and Paul H.
Garthwaite. A comparative evaluation of algorithms for discovering
translational patterns in Baroque keyboard works. In J.S. Downie and R.
Veltkamp (Eds), Proc ISMIR, pp. 3-8, Utrecht, 2010.

Establishment Precision, Recall and F1 Score
--------------------------------------------

This metric evaluates the amount of patterns that were successfully identified
by the estimated results, no matter how many occurrences they found.
In other words, this metric captures how the algorithm successfully
_established_ that a pattern repeated at least twice, and this pattern is also
found in the reference annotation.

Occurrence Precision, Recall and F1 Score
-----------------------------------------

Evaluation of how well an estimation can effectively identify all the
occurrences of the found patterns, independently of how many patterns have
been discovered. This metric has a threshold parameter that indicates how
similar two occurrences must be in order to be considered equal.

In MIREX, this evaluation is run twice, with thresholds .75 and .5.

Three-layer Precision, Recall and F1 Score
------------------------------------------

This metric aims to evaluate the general similarity between the reference and
the estimations, combining both the establishment of patterns and the
retrieval of its occurrences in a single F1 score.

Proposed by David Meridith in personal correspondance with Tom Collins in 2013,
and formally described in:

Tom Collins 2014 (TODO).

First N patterns metrics
------------------------

This includes the first N patterns target proportion establishment recall,
and the first N patterns three-layer precision. By analyzing the first N
patterns only, we evaluate the ability of the algorithm of sorting the
identified patterns based on their relevance. Both metrics are used in the
MIREX evaluation.


Written by Oriol Nieto (oriol@nyu.edu), 2014
"""


import numpy as np
from . import util
import warnings
import collections


def _n_onset_midi(patterns):
    ''' Computes the number of onset_midi objects in a pattern '''
    return len([o_m for pat in patterns for occ in pat for o_m in occ])


def validate(reference_patterns, estimated_patterns):
    """Checks that the input annotations to a metric look like valid pattern
    lists, and throws helpful errors if not.

    :parameters:
        - reference_patterns : list
            The reference patterns using the format returned by
            :func:`mir_eval.io.load_patterns()`
        - estimated_patterns : list
            The estimated patterns in the same format
    """
    # Warn if pattern lists are empty
    if _n_onset_midi(reference_patterns) == 0:
        warnings.warn('Reference patterns are empty.')
    if _n_onset_midi(estimated_patterns) == 0:
        warnings.warn('Estimated patterns are empty.')
    for patterns in [reference_patterns, estimated_patterns]:
        for pattern in patterns:
            if len(pattern) <= 0:
                raise ValueError("Each pattern must contain at least one "
                                 "occurrence.")
            for occurrence in pattern:
                for onset_midi in occurrence:
                    if len(onset_midi) != 2:
                        raise ValueError("The (onset, midi) tuple must "
                                         "contain exactly 2 elements.")


def _occurrence_intersection(occ_P, occ_Q):
    """Computes the intersection between two occurrences.

    :parameters:
        - occ_P : list of tuples
            (onset, midi) pairs representing the reference occurrence.
        - occ_Q : list
            second list of (onset, midi) tuples

    :returns:
        - S : set
            Set of the intersection between occ_P and occ_Q.
    """
    set_P = set([tuple(onset_midi) for onset_midi in occ_P])
    set_Q = set([tuple(onset_midi) for onset_midi in occ_Q])
    return set_P & set_Q    # Return the intersection


def _compute_score_matrix(P, Q, similarity_metric="cardinality_score"):
    """Computes the score matrix between the patterns P and Q.

    :parameters:
        - P : list
            Pattern containing a list of occurrences.

        - Q : list
            Pattern containing a list of occurrences.

        - similarity_metric : str
            A string representing the metric to be used
            when computing the similarity matrix. Accepted values:
            - "cardinality_score":
                Count of the intersection between occurrences.

    :returns:
        - sm : np.array
            The score matrix between P and Q using the similarity_metric.
    """
    sm = np.zeros((len(P), len(Q)))     # The score matrix
    for iP, occ_P in enumerate(P):
        for iQ, occ_Q in enumerate(Q):
            if similarity_metric == "cardinality_score":
                denom = float(np.max([len(occ_P), len(occ_Q)]))
                # Compute the score
                sm[iP, iQ] = len(_occurrence_intersection(occ_P, occ_Q)) / \
                    denom
            # TODO: More scores: 'normalised matching socre'
            else:
                raise ValueError("The similarity metric (%s) can only be: "
                                 "'cardinality_score'.")
    return sm


def standard_FPR(reference_patterns, estimated_patterns, tol=1e-5):
    """Standard F1 Score, Precision and Recall.

    This metric checks if the prorotype patterns of the reference match
    possible translated patterns in the prototype patterns of the estimations.
    Since the sizes of these prototypes must be equal, this metric is quite
    restictive and it tends to be 0 in most of 2013 MIREX results.

    :usage:
        >>> ref_patterns = mir_eval.io.load_patterns("ref_pattern.txt")
        >>> est_patterns = mir_eval.io.load_patterns("est_pattern.txt")
        >>> F, P, R = mir_eval.pattern.standard_FPR(ref_patterns, est_patterns)

    :params:
        - reference_patterns : list
            The reference patterns using the format returned by
            :func:`mir_eval.io.load_patterns()`
        - estimated_patterns : list
            The estimated patterns in the same format
        - tol : float
            Tolerance level when comparing reference against estimation.
            Default parameter is the one found in the original matlab code by
            Tom Collins used for MIREX 2013.

    :returns:
        - f_measure : float
            The standard F1 Score
        - precision : float
            The standard Precision
        - recall : float
            The standard Recall
    """
    validate(reference_patterns, estimated_patterns)
    nP = len(reference_patterns)    # Number of patterns in the reference
    nQ = len(estimated_patterns)    # Number of patterns in the estimation
    k = 0                           # Number of patterns that match

    # If no patterns were provided, metric is zero
    if _n_onset_midi(reference_patterns) == 0 or \
       _n_onset_midi(estimated_patterns) == 0:
        return 0., 0., 0.

    # Find matches of the prototype patterns
    for ref_pattern in reference_patterns:
        P = np.asarray(ref_pattern[0])      # Get reference prototype
        for est_pattern in estimated_patterns:
            Q = np.asarray(est_pattern[0])  # Get estimation prototype

            if len(P) != len(Q):
                continue

            # Check transposition given a certain tolerance
            if np.max(np.abs(np.diff(P - Q, axis=0))) < tol:
                k += 1
                break

    # Compute the standard measures
    precision = k / float(nQ)
    recall = k / float(nP)
    f_measure = util.f_measure(precision, recall)
    return f_measure, precision, recall


def establishment_FPR(reference_patterns, estimated_patterns,
                      similarity_metric="cardinality_score"):
    """Establishment F1 Score, Precision and Recall.

    :usage:
        >>> ref_patterns = mir_eval.io.load_patterns("ref_pattern.txt")
        >>> est_patterns = mir_eval.io.load_patterns("est_pattern.txt")
        >>> F, P, R = mir_eval.pattern.establishment_FPR(ref_patterns,
                                                         est_patterns)

    :params:
        - reference_patterns : list
            The reference patterns in the format returned by
            :func:`mir_eval.io.load_patterns()`
        - estimated_patterns : list
            The estimated patterns in the same format
        -  similarity_metric : str
            A string representing the metric to be used when computing the
            similarity matrix. Accepted values:

                - "cardinality_score":
                    Count of the intersection between occurrences.

    :returns:
        - f_measure : float
            The establishment F1 Score
        - precision : float
            The establishment Precision
        - recall : float
            The establishment Recall
    """
    validate(reference_patterns, estimated_patterns)
    nP = len(reference_patterns)    # Number of elements in reference
    nQ = len(estimated_patterns)    # Number of elements in estimation
    S = np.zeros((nP, nQ))          # Establishment matrix

    # If no patterns were provided, metric is zero
    if _n_onset_midi(reference_patterns) == 0 or \
       _n_onset_midi(estimated_patterns) == 0:
        return 0., 0., 0.

    for iP, ref_pattern in enumerate(reference_patterns):
        for iQ, est_pattern in enumerate(estimated_patterns):
            s = _compute_score_matrix(ref_pattern, est_pattern,
                                      similarity_metric)
            S[iP, iQ] = np.max(s)

    # Compute scores
    precision = np.mean(np.max(S, axis=0))
    recall = np.mean(np.max(S, axis=1))
    f_measure = util.f_measure(precision, recall)
    return f_measure, precision, recall


def occurrence_FPR(reference_patterns, estimated_patterns, thres=.75,
                   similarity_metric="cardinality_score"):
    """Establishment F1 Score, Precision and Recall.

    :usage:
        >>> ref_patterns = mir_eval.io.load_patterns("ref_pattern.txt")
        >>> est_patterns = mir_eval.io.load_patterns("est_pattern.txt")
        >>> F, P, R = mir_eval.pattern.occurrence_FPR(ref_patterns,
                                                      est_patterns)

    :params:
        - reference_patterns : list
            The reference patterns in the format returned by
            :func:`mir_eval.io.load_patterns()`
        - estimated_patterns : list
            The estimated patterns in the same format
        - thres : float
            How similar two occcurrences must be in order to be considered
            equal
        - similarity_metric : str
            A string representing the metric to be used
            when computing the similarity matrix. Accepted values:

                - "cardinality_score":
                    Count of the intersection between occurrences.

    :returns:
        - f_measure : float
            The establishment F1 Score
        - precision : float
            The establishment Precision
        - recall : float
            The establishment Recall
    """
    validate(reference_patterns, estimated_patterns)
    # Number of elements in reference
    nP = len(reference_patterns)
    # Number of elements in estimation
    nQ = len(estimated_patterns)
    # Occurrence matrix with Precision and recall in its last dimension
    O_PR = np.zeros((nP, nQ, 2))

    # Index of the values that are greater than the specified threshold
    rel_idx = np.empty((0, 2), dtype=int)

    # If no patterns were provided, metric is zero
    if _n_onset_midi(reference_patterns) == 0 or \
       _n_onset_midi(estimated_patterns) == 0:
        return 0., 0., 0.

    for iP, ref_pattern in enumerate(reference_patterns):
        for iQ, est_pattern in enumerate(estimated_patterns):
            s = _compute_score_matrix(ref_pattern, est_pattern,
                                      similarity_metric)
            if np.max(s) >= thres:
                O_PR[iP, iQ, 0] = np.mean(np.max(s, axis=0))
                O_PR[iP, iQ, 1] = np.mean(np.max(s, axis=1))
                rel_idx = np.vstack((rel_idx, [iP, iQ]))

    # Compute the scores
    if len(rel_idx) == 0:
        precision = 0
        recall = 0
    else:
        P = O_PR[:, :, 0]
        precision = np.mean(np.max(P[np.ix_(rel_idx[:, 0], rel_idx[:, 1])],
                                   axis=0))
        R = O_PR[:, :, 1]
        recall = np.mean(np.max(R[np.ix_(rel_idx[:, 0], rel_idx[:, 1])],
                                axis=1))
    f_measure = util.f_measure(precision, recall)
    return f_measure, precision, recall


def three_layer_FPR(reference_patterns, estimated_patterns):
    """Three Layer F1 Score, Precision and Recall. As described by Meridith.

    TODO: Add publication. Collins 2014?

    :usage:
        >>> ref_patterns = mir_eval.io.load_patterns("ref_pattern.txt")
        >>> est_patterns = mir_eval.io.load_patterns("est_pattern.txt")
        >>> F, P, R = mir_eval.pattern.three_layer_FPR(ref_patterns,
                                                       est_patterns)

    :params:
        - reference_patterns : list
            The reference patterns in the format returned by
            :func:`mir_eval.io.load_patterns()`
        - estimated_patterns : list
            The estimated patterns in the same format

    :returns:
        - f_measure : float
            The three-layer F1 Score
        - precision : float
            The three-layer Precision
        - recall : float
            The three-layer Recall
    """
    validate(reference_patterns, estimated_patterns)

    def compute_first_layer_PR(ref_occs, est_occs):
        """Computes the first layer Precision and Recall values given the
        set of occurrences in the reference and the set of occurrences in the
        estimation."""
        # Find the length of the intersection between reference and estimation
        s = len(_occurrence_intersection(ref_occs, est_occs))

        # Compute the first layer scores
        precision = s / float(len(ref_occs))
        recall = s / float(len(est_occs))
        return precision, recall

    def compute_second_layer_PR(ref_pattern, est_pattern):
        """Computes the second layer Precision and Recall values given the
        set of occurrences in the reference and the set of occurrences in the
        estimation."""
        # Compute the first layer scores
        F_1 = compute_layer(ref_pattern, est_pattern)

        # Compute the second layer scores
        precision = np.mean(np.max(F_1, axis=0))
        recall = np.mean(np.max(F_1, axis=1))
        return precision, recall

    def compute_layer(ref_elements, est_elements, layer=1):
        """Computes the F-measure matrix for a given layer. The reference and
        estimated elements can be either patters or occurrences, depending
        on the layer.

        For layer 1, the elements must be occurrences.
        For layer 2, the elements must be patterns.
        """
        if layer != 1 and layer != 2:
            raise ValueError("Layer (%d) must be an integer between 1 and 2"
                             % layer)

        nP = len(ref_elements)      # Number of elements in reference
        nQ = len(est_elements)      # Number of elements in estimation
        F = np.zeros((nP, nQ))      # F-measure matrix for the given layer
        for iP in xrange(nP):
            for iQ in xrange(nQ):
                if layer == 1:
                    func = compute_first_layer_PR
                elif layer == 2:
                    func = compute_second_layer_PR

                # Compute layer scores
                precision, recall = func(ref_elements[iP], est_elements[iQ])
                F[iP, iQ] = util.f_measure(precision, recall)
        return F

    # If no patterns were provided, metric is zero
    if _n_onset_midi(reference_patterns) == 0 or \
       _n_onset_midi(estimated_patterns) == 0:
        return 0., 0., 0.

    # Compute the second layer (it includes the first layer)
    F_2 = compute_layer(reference_patterns, estimated_patterns, layer=2)

    # Compute the final scores (third layer)
    precision_3 = np.mean(np.max(F_2, axis=0))
    recall_3 = np.mean(np.max(F_2, axis=1))
    f_measure_3 = util.f_measure(precision_3, recall_3)
    return f_measure_3, precision_3, recall_3


def first_n_three_layer_P(reference_patterns, estimated_patterns, n=5):
    """First n three-layer precision.

    This metric is basically the same as the three-layer FPR but it is only
    applied to the first n estimated patterns, and it only returns the
    precision. In MIREX and typically, n = 5.

    :usage:
        >>> ref_patterns = mir_eval.io.load_patterns("ref_pattern.txt")
        >>> est_patterns = mir_eval.io.load_patterns("est_pattern.txt")
        >>> P = mir_eval.pattern.first_n_three_layer_P(ref_patterns,
                                                       est_patterns, n=5)

    :params:
        - reference_patterns : list
            The reference patterns in the format returned by
            :func:`mir_eval.io.load_patterns()`
        - estimated_patterns : list
            The estimated patterns in the same format
        - n : int
            Number of patterns to consider from the estimated results, in
            the order they appear in the matrix

    :returns:
        - precision : float
            The first n three-layer Precision
    """

    validate(reference_patterns, estimated_patterns)
    # If no patterns were provided, metric is zero
    if _n_onset_midi(reference_patterns) == 0 or \
       _n_onset_midi(estimated_patterns) == 0:
        return 0., 0., 0.

    # Get only the first n patterns from the estimated results
    fn_est_patterns = estimated_patterns[:min(len(estimated_patterns), n)]

    # Compute the three-layer scores for the first n estimated patterns
    F, P, R = three_layer_FPR(reference_patterns, fn_est_patterns)

    return P    # Return the precision only


def first_n_target_proportion_R(reference_patterns, estimated_patterns, n=5):
    """Firt n target proportion establishment recall metric.

    This metric is similar is similar to the establishment FPR score, but it
    only takes into account the first n estimated patterns and it only
    outputs the Recall value of it.

    :usage:
        >>> ref_patterns = mir_eval.io.load_patterns("ref_pattern.txt")
        >>> est_patterns = mir_eval.io.load_patterns("est_pattern.txt")
        >>> R = mir_eval.pattern.first_n_target_proportion_R(
                                            ref_patterns, est_patterns, n=5)

    :params:
        - reference_patterns : list
            The reference patterns in the format returned by
            :func:`mir_eval.io.load_patterns()`
        - estimated_patterns : list
            The estimated patterns in the same format
        - n : int
            Number of patterns to consider from the estimated results, in
            the order they appear in the matrix.

    :returns:
        - recall : float
            The first n target proportion Recall.
    """

    validate(reference_patterns, estimated_patterns)
    # If no patterns were provided, metric is zero
    if _n_onset_midi(reference_patterns) == 0 or \
       _n_onset_midi(estimated_patterns) == 0:
        return 0., 0., 0.

    # Get only the first n patterns from the estimated results
    fn_est_patterns = estimated_patterns[:min(len(estimated_patterns), n)]

    F, P, R = establishment_FPR(reference_patterns, fn_est_patterns)
    return R


def evaluate(ref_patterns, est_patterns, **kwargs):
    '''
    Load data and perform the evaluation.

    :params:
        - ref_patterns : list
            The reference patterns in the format returned by
            :func:`mir_eval.io.load_patterns()`
        - est_patterns : list
            The estimated patterns in the same format
        - kwargs
            Additional keyword arguments which will be passed to the
            appropriate metric or preprocessing functions.

    :returns:
        - scores : dict
            Dictionary of scores, where the key is the metric name (str) and
            the value is the (float) score achieved.
    '''

    # Now compute all the metrics
    scores = collections.OrderedDict()

    # Standard scores
    scores['F'], scores['P'], scores['R'] = \
        util.filter_kwargs(standard_FPR, ref_patterns, est_patterns, **kwargs)

    # Establishment scores
    scores['F_est'], scores['P_est'], scores['R_est'] = \
        util.filter_kwargs(establishment_FPR, ref_patterns, est_patterns,
                           **kwargs)

    # Occurrence scores
    # Force these values for thresh
    kwargs['thresh'] = .5
    scores['F_occ.5'], scores['P_occ.5'], scores['R_occ.5'] = \
        util.filter_kwargs(occurrence_FPR, ref_patterns, est_patterns,
                           **kwargs)
    kwargs['thresh'] = .75
    scores['F_occ.75'], scores['P_occ.75'], scores['R_occ.75'] = \
        util.filter_kwargs(occurrence_FPR, ref_patterns, est_patterns,
                           **kwargs)

    # Three-layer scores
    scores['F_3'], scores['P_3'], scores['R_3'] = \
        util.filter_kwargs(three_layer_FPR, ref_patterns, est_patterns,
                           **kwargs)

    # First Five Patterns scores
    # Set default value of n
    if 'n' not in kwargs:
        kwargs['n'] = 5
    scores['FFP'] = util.filter_kwargs(first_n_three_layer_P, ref_patterns,
                                       est_patterns, **kwargs)
    scores['FFTP_est'] = \
        util.filter_kwargs(first_n_target_proportion_R, ref_patterns,
                           est_patterns, **kwargs)

    return scores
