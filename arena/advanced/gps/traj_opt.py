""" This file defines the base trajectory optimization class. """
import abc
import logging
import copy
from collections import namedtuple, OrderedDict

import numpy as np
from numpy.linalg import LinAlgError
import scipy as sp

from arena.advanced.gps.config import TRAJ_OPT_LQR
from arena.advanced.gps.utils import LineSearch, traj_distr_kl, BundleType

LOGGER = logging.getLogger(__name__)


class TrajectoryInfo(BundleType):
    """ Collection of trajectory-related variables. """
    def __init__(self):
        variables = {
            'dynamics': None,  # Dynamics object for the current iteration.
            'x0mu': None,  # Mean for the initial state, used by the dynamics.
            'x0sigma': None,  # Covariance for the initial state distribution.
            'cc': None,  # Cost estimate constant term.
            'cv': None,  # Cost estimate vector term.
            'Cm': None,  # Cost estimate matrix term.
            'cs': None,  # true costs
            'last_kl_step': float('inf'),  # KL step of the previous iteration.
        }
        BundleType.__init__(self, variables)


""" LQR trajectory optimization, Python implementation. """
class TrajOptLQRPython(object):
    def __init__(self, hyperparams=None):
        config = copy.deepcopy(TRAJ_OPT_LQR)
        config.update(hyperparams)

        self._hyperparams = config

    """ Run dual gradient decent to optimize trajectories. """
    def update(self, traj_info, cur_traj_distr, step_mult, cur_eta, base_kl_step):
        T = traj_info.cc.shape[0]
        prev_traj_distr = cur_traj_distr
        prev_eta = cur_eta

        # if type(algorithm) == AlgorithmMDGPS:
            # For MDGPS, constrain to previous NN linearization
            # prev_traj_distr = algorithm.cur[m].pol_info.traj_distr()
        # else:
            # For BADMM/trajopt, constrain to previous LG controller

        # Set KL-divergence step size (epsilon).
        kl_step = base_kl_step * step_mult

        line_search = LineSearch(self._hyperparams['min_eta'])
        min_eta = -np.Inf

        for itr in range(self._hyperparams['DGD_MAX_ITER']):
            traj_distr, new_eta = self.backward(prev_traj_distr, traj_info,
                                                prev_eta)
            new_mu, new_sigma = self.forward(traj_distr, traj_info)

            # Update min eta if we had a correction after running bwd.
            if new_eta > prev_eta:
                min_eta = new_eta

            # Compute KL divergence between prev and new distribution.
            kl_div = traj_distr_kl(new_mu, new_sigma,
                                   traj_distr, prev_traj_distr)

            traj_info.last_kl_step = kl_div

            # Main convergence check - constraint satisfaction.
            if (abs(kl_div - kl_step*T) < 0.1*kl_step*T or
                    (itr >= 20 and kl_div < kl_step*T)):
                LOGGER.debug("Iteration %i, KL: %f / %f converged",
                             itr, kl_div, kl_step * T)
                eta = prev_eta  # TODO - Should this be here?
                break

            # Adjust eta using bracketing line search.
            eta = line_search.bracketing_line_search(kl_div - kl_step*T,
                                                     new_eta, min_eta)

            # Convergence check - dual variable change when min_eta hit.
            if (abs(prev_eta - eta) < self._hyperparams['THRESHA'] and
                    eta == max(min_eta, self._hyperparams['min_eta'])):
                LOGGER.debug("Iteration %i, KL: %f / %f converged (eta limit)",
                             itr, kl_div, kl_step * T)
                break

            # Convergence check - constraint satisfaction, KL not
            # changing much.
            if (itr > 2 and abs(kl_div - prev_kl_div) < self._hyperparams['THRESHB'] and
                    kl_div < kl_step*T):
                LOGGER.debug("Iteration %i, KL: %f / %f converged (no change)",
                             itr, kl_div, kl_step * T)
                break

            prev_kl_div = kl_div
            LOGGER.debug('Iteration %i, KL: %f / %f eta: %f -> %f',
                         itr, kl_div, kl_step * T, prev_eta, eta)
            prev_eta = eta

        if kl_div > kl_step*T and abs(kl_div - kl_step*T) > 0.1*kl_step*T:
            LOGGER.warning(
                "Final KL divergence after DGD convergence is too high."
            )

        return traj_distr, eta

    def estimate_cost(self, traj_distr, traj_info):
        """ Compute Laplace approximation to expected cost. """
        # Constants.
        T = traj_distr.T

        # Perform forward pass (note that we repeat this here, because
        # traj_info may have different dynamics from the ones that were
        # used to compute the distribution already saved in traj).
        mu, sigma = self.forward(traj_distr, traj_info)

        # Compute cost.
        predicted_cost = np.zeros(T)
        for t in range(T):
            predicted_cost[t] = traj_info.cc[t] + 0.5 * \
                    np.sum(sigma[t, :, :] * traj_info.Cm[t, :, :]) + 0.5 * \
                    mu[t, :].T.dot(traj_info.Cm[t, :, :]).dot(mu[t, :]) + \
                    mu[t, :].T.dot(traj_info.cv[t, :])
        return predicted_cost

    def compute_costs(self, traj_distr, traj_info, eta):
        """ Compute cost estimates """
        fCm, fcv = traj_info.Cm / eta, traj_info.cv / eta
        K, ipc, k = traj_distr.K, traj_distr.inv_pol_covar, traj_distr.k

        T = traj_info.Cm.shape[0]
        # Add in the trajectory divergence term.
        for t in range(T - 1, -1, -1):
            fCm[t, :, :] += np.vstack([
                np.hstack([
                    K[t, :, :].T.dot(ipc[t, :, :]).dot(K[t, :, :]),
                    -K[t, :, :].T.dot(ipc[t, :, :])
                ]),
                np.hstack([
                    -ipc[t, :, :].dot(K[t, :, :]), ipc[t, :, :]
                ])
            ])
            fcv[t, :] += np.hstack([
                K[t, :, :].T.dot(ipc[t, :, :]).dot(k[t, :]),
                -ipc[t, :, :].dot(k[t, :])
            ])

        return fCm, fcv

    def forward(self, traj_distr, traj_info):
        """
        Perform LQR forward pass. Computes state-action marginals from
        dynamics and policy.
        Args:
            traj_distr: A linear Gaussian policy object.
            traj_info: A TrajectoryInfo object.
        Returns:
            mu: A T x dX mean action vector.
            sigma: A T x dX x dX covariance matrix.
        """
        # Compute state-action marginals from specified conditional
        # parameters and current traj_info.
        T = traj_distr.T
        dU = traj_distr.dU
        dX = traj_distr.dX

        # Constants.
        idx_x = slice(dX)

        # Allocate space.
        sigma = np.zeros((T, dX+dU, dX+dU))
        mu = np.zeros((T, dX+dU))

        # Pull out dynamics.
        Fm = traj_info.dynamics.Fm
        fv = traj_info.dynamics.fv
        dyn_covar = traj_info.dynamics.dyn_covar

        # Set initial covariance (initial mu is always zero).
        sigma[0, idx_x, idx_x] = traj_info.x0sigma
        mu[0, idx_x] = traj_info.x0mu

        for t in range(T):
            sigma[t, :, :] = np.vstack([
                np.hstack([
                    sigma[t, idx_x, idx_x],
                    sigma[t, idx_x, idx_x].dot(traj_distr.K[t, :, :].T)
                ]),
                np.hstack([
                    traj_distr.K[t, :, :].dot(sigma[t, idx_x, idx_x]),
                    traj_distr.K[t, :, :].dot(sigma[t, idx_x, idx_x]).dot(
                        traj_distr.K[t, :, :].T
                    ) + traj_distr.pol_covar[t, :, :]
                ])
            ])
            mu[t, :] = np.hstack([
                mu[t, idx_x],
                traj_distr.K[t, :, :].dot(mu[t, idx_x]) + traj_distr.k[t, :]
            ])
            if t < T - 1:
                sigma[t+1, idx_x, idx_x] = \
                        Fm[t, :, :].dot(sigma[t, :, :]).dot(Fm[t, :, :].T) + \
                        dyn_covar[t, :, :]
                mu[t+1, idx_x] = Fm[t, :, :].dot(mu[t, :]) + fv[t, :]
        return mu, sigma

    def backward(self, prev_traj_distr, traj_info, eta):
        """
        Perform LQR backward pass. This computes a new linear Gaussian
        policy object.
        Args:
            prev_traj_distr: A linear Gaussian policy object from
                previous iteration.
            traj_info: A TrajectoryInfo object.
            eta: Dual variable.
            algorithm: Algorithm object needed to compute costs.
            m: Condition number.
        Returns:
            traj_distr: A new linear Gaussian policy.
            new_eta: The updated dual variable. Updates happen if the
                Q-function is not PD.
        """
        # Constants.
        T = prev_traj_distr.T
        dU = prev_traj_distr.dU
        dX = prev_traj_distr.dX

        traj_distr = prev_traj_distr.nans_like()

        # Store pol_wt if necessary
        # if type(algorithm) == AlgorithmBADMM:
        #     pol_wt = algorithm.cur[m].pol_info.pol_wt

        idx_x = slice(dX)
        idx_u = slice(dX, dX+dU)

        # Pull out dynamics.
        Fm = traj_info.dynamics.Fm
        fv = traj_info.dynamics.fv

        # Non-SPD correction terms.
        del_ = self._hyperparams['del0']
        eta0 = eta

        # Run dynamic programming.
        fail = True
        while fail:
            fail = False  # Flip to true on non-symmetric PD.

            # Allocate.
            Vxx = np.zeros((T, dX, dX))
            Vx = np.zeros((T, dX))

            fCm, fcv = self.compute_costs(prev_traj_distr, traj_info, eta)

            # Compute state-action-state function at each time step.
            for t in range(T - 1, -1, -1):
                # Add in the cost.
                Qtt = fCm[t, :, :]  # (X+U) x (X+U)
                Qt = fcv[t, :]  # (X+U) x 1

                # Add in the value function from the next time step.
                if t < T - 1:
                    # if type(algorithm) == AlgorithmBADMM:
                    #     multiplier = (pol_wt[t+1] + eta)/(pol_wt[t] + eta)
                    # else:
                    multiplier = 1.0
                    Qtt = Qtt + multiplier * \
                            Fm[t, :, :].T.dot(Vxx[t+1, :, :]).dot(Fm[t, :, :])
                    Qt = Qt + multiplier * \
                            Fm[t, :, :].T.dot(Vx[t+1, :] +
                                            Vxx[t+1, :, :].dot(fv[t, :]))

                # Symmetrize quadratic component.
                Qtt = 0.5 * (Qtt + Qtt.T)

                # Compute Cholesky decomposition of Q function action
                # component.
                try:
                    U = sp.linalg.cholesky(Qtt[idx_u, idx_u])
                    L = U.T
                except LinAlgError as e:
                    # Error thrown when Qtt[idx_u, idx_u] is not
                    # symmetric positive definite.
                    LOGGER.debug('LinAlgError: %s', e)
                    fail = True
                    break

                # Store conditional covariance, inverse, and Cholesky.
                traj_distr.inv_pol_covar[t, :, :] = Qtt[idx_u, idx_u]
                traj_distr.pol_covar[t, :, :] = sp.linalg.solve_triangular(
                    U, sp.linalg.solve_triangular(L, np.eye(dU), lower=True)
                )
                traj_distr.chol_pol_covar[t, :, :] = sp.linalg.cholesky(
                    traj_distr.pol_covar[t, :, :]
                )

                # Compute mean terms.
                traj_distr.k[t, :] = -sp.linalg.solve_triangular(
                    U, sp.linalg.solve_triangular(L, Qt[idx_u], lower=True)
                )
                traj_distr.K[t, :, :] = -sp.linalg.solve_triangular(
                    U, sp.linalg.solve_triangular(L, Qtt[idx_u, idx_x],
                                                  lower=True)
                )

                # Compute value function.
                Vxx[t, :, :] = Qtt[idx_x, idx_x] + \
                        Qtt[idx_x, idx_u].dot(traj_distr.K[t, :, :])
                Vx[t, :] = Qt[idx_x] + Qtt[idx_x, idx_u].dot(traj_distr.k[t, :])
                Vxx[t, :, :] = 0.5 * (Vxx[t, :, :] + Vxx[t, :, :].T)

            # Increment eta on non-SPD Q-function.
            if fail:
                old_eta = eta
                eta = eta0 + del_
                LOGGER.debug('Increasing eta: %f -> %f', old_eta, eta)
                del_ *= 2  # Increase del_ exponentially on failure.
                if eta >= 1e16:
                    if np.any(np.isnan(Fm)) or np.any(np.isnan(fv)):
                        raise ValueError('NaNs encountered in dynamics!')
                    raise ValueError('Failed to find PD solution even for very \
                            large eta (check that dynamics and cost are \
                            reasonably well conditioned)!')
        return traj_distr, eta