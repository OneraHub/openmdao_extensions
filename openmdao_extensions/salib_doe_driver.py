"""
Driver for running model on design of experiments cases using Salib sampling methods
"""
from __future__ import print_function
from six import itervalues, iteritems, reraise
from six.moves import range

import numpy as np

from openmdao.api import DOEDriver, ListGenerator, OptionsDictionary
from openmdao.core.driver import Driver, RecordingDebugging
from openmdao.drivers.doe_generators import DOEGenerator
from openmdao.utils.general_utils import warn_deprecation

SALIB_NOT_INSTALLED = False
try:
    from SALib.sample import morris as ms
except ImportError:
    SALIB_NOT_INSTALLED = True

class SalibDOEGenerator(DOEGenerator):

    def __init__(self):
        if SALIB_NOT_INSTALLED:
            raise RuntimeError('SALib library is not installed. \
                                cf. https://salib.readthedocs.io/en/latest/getting-started.html')
        self._cases = []
        self._pb = None
        self.called = False

    def __call__(self, design_vars, model=None):
        bounds=[]
        names=[]
        for name, meta in iteritems(design_vars):
            size = meta['size']
            meta_low = meta['lower']
            meta_high = meta['upper']
            for j in range(size):
                if isinstance(meta_low, np.ndarray):
                    p_low = meta_low[j]
                else:
                    p_low = meta_low

                if isinstance(meta_high, np.ndarray):
                    p_high = meta_high[j]
                else:
                    p_high = meta_high
                    
                display_name = name.split('.')[-1]
                if size>1:
                    display_name += str(j)
                names.append(display_name)
                bounds.append((p_low, p_high))

        self._pb = {'num_vars': len(names), 
                    'names': names, 
                    'bounds': bounds, 'groups': None}
        self._compute_cases()
        self.called = True
        sample = []
        for i in range(self._cases.shape[0]):
            j=0
            for name, meta in iteritems(design_vars):
                size = meta['size']
                sample.append((name, self._cases[i, j:j + size]))
                j += size
            yield sample

    def _compute_cases(self):
        raise RuntimeError("Have to be implemented in subclass.")

    def get_cases(self):
        if not self.called:
            raise RuntimeError("Have to run the driver before getting cases")
        return self._cases

    def get_salib_problem(self):
        if not self.called:
            raise RuntimeError("Have to run the driver before getting the SALib problem")
        return self._pb

class SalibMorrisDOEGenerator(SalibDOEGenerator):

    def __init__(self, n_trajs=2, n_levels=4):
        super(SalibMorrisDOEGenerator, self).__init__()
        # number of trajectories to apply morris method
        self.n_trajs = n_trajs
        # number of grid levels
        self.n_levels = n_levels

    def _compute_cases(self):
        self._cases = ms.sample(self._pb, self.n_trajs, self.n_levels)

class SalibDOEDriver(DOEDriver):
    """
    Baseclass for SALib design-of-experiments Drivers
    """
    def __init__(self, **kwargs):
        super(SalibDOEDriver, self).__init__()

        if SALIB_NOT_INSTALLED:
            raise RuntimeError('SALib library is not installed. \
                                cf. https://salib.readthedocs.io/en/latest/getting-started.html')

        self.options.declare('sa_method_name', default='Morris', values=['Morris', 'Sobol'],
                             desc='either Morris or Sobol')
        self.options.declare('sa_doe_options', types=dict, default={},
                             desc='options for given SMT sensitivity analysis method')
        self.options.update(kwargs)

        self.sa_settings = OptionsDictionary()
        if self.options['sa_method_name'] == 'Morris':
            self.sa_settings.declare('n_trajs', types=int, default=2,
                                             desc='number of trajectories to apply morris method')
            self.sa_settings.declare('n_levels', types=int, default=4,
                                             desc='number of grid levels')
            self.sa_settings.update(self.options['sa_doe_options'])
            n_trajs = self.sa_settings['n_trajs']
            n_levels = self.sa_settings['n_levels']
            self.options['generator'] = SalibMorrisDOEGenerator(n_trajs, n_levels)
        elif self.options['sa_method_name'] == 'Sobol':
            raise RuntimeError('sa with Sobol method not yet implemented')
        else:
            raise RuntimeError("Bad sensitivity analysis method name '{}'".format(self.options['sa_method_name']))

    def _set_name(self):
        self._name = 'SALib_DOE_'+self.options['sa_method_name']

    def get_cases(self):
        return self.options['generator'].get_cases()

    def get_salib_problem(self):
        return self.options['generator'].get_salib_problem()


