#!/usr/bin/env python
#
# Garrett Granroth <granrothge@ornl.gov>
import os, numpy as np
import pytest
from dgsres.singlextal.PSF_Affine_Model import gaus
from dgsres.singlextal.workflow import create_interp_model, print_parameter_table
import imp
import time
import cloudpickle as pkl
interactive=False

ts = time.time()

@pytest.fixture
def init_dec():
    here = os.path.abspath(os.path.dirname(__file__))
    workdir = os.path.join(here,'SEQUOIA_data','')
    with open(os.path.join(workdir,'test_slice-fit_results.pkl'), 'rb') as fh:
        qE2fitres = pkl.load(fh)
    os.chdir(workdir)
   
    print("time = {} s".format(time.time()-ts))
    return [qE2fitres]


def test_create_interp_model(init_dec):
    qE2fitres = init_dec[0]
    test = create_interp_model(qE2fitres, None)
    assert len(test.qE_points)==118
    assert np.all(np.abs(np.array(test.qE_points[0]) - np.array((-4.0, -10.0))) < 1e-6)
    assert np.all(np.abs(np.array(test.qE_points[-1]) - np.array((3.5, 50.0))) < 1e-6)
    kys = set(['alpha', 'beta', 'xp_center', 'xp_sigma', 'y_sigma_left', 'y_sigma_right', 'y_weight_left', 
               'y_ef_width', 'y_offset', 'scale'])
    pkys = set(list(test.param_values.keys()))
    kyi = kys.difference(pkys)
    assert len(kyi) == 0
    assert np.abs(test.qrange - 1.38) < 1e-6
    assert np.abs(test.Erange - 11.8) < 1e-6
    return

def test_print_parameter_table(init_dec):
    qE2fitres = init_dec[0]
    print_parameter_table(qE2fitres)





# End of file
