from __future__ import division
import numpy
import sys
import time

from openmdao.api import IndepVarComp, Problem, Group, ScipyOptimizer, Newton, ScipyGMRES, LinearGaussSeidel, NLGaussSeidel, SqliteRecorder
from geometry import GeometryMesh, mesh_gen
from transfer import TransferDisplacements, TransferLoads
from weissinger import WeissingerGroup
from spatialbeam import SpatialBeamGroup
from functionals import FunctionalBreguetRange, FunctionalEquilibrium

from gs_newton import HybridGSNewton

mesh = mesh_gen(n_points_inboard=2, n_points_outboard=3)
num_y = mesh.shape[1]

span = 1.
cons = numpy.array([int((num_y-1)/2)])

W0 = 1.e5
CT = 0.01
a = 200
M = 0.75
R = 2000

v = a * M
alpha = 1.
rho = 1.225

E = 200.e10
G = 60.e9
stress = 20.e6
mrho = 3.e3
r = 0.3 * numpy.ones(num_y-1)
# t = 0.05 * numpy.ones(num_y-1)
t = 0.05 * numpy.ones(num_y-1)

root = Group()


des_vars = [
    ('span', span),
    ('twist', numpy.zeros(num_y)), 
    ('v', v),
    ('alpha', alpha), 
    ('rho', rho),
    ('r', r),  
    ('t', t), 
]

root.add('des_vars', 
         IndepVarComp(des_vars), 
         promotes=['*'])

coupled = Group() # LU_Group
coupled.add('mesh',
            GeometryMesh(mesh),
            promotes=['*'])
coupled.add('def_mesh',
            TransferDisplacements(num_y),
            promotes=['*'])
coupled.add('weissinger',
            WeissingerGroup(num_y),
            promotes=['*'])
coupled.add('loads',
            TransferLoads(num_y),
            promotes=['*'])
coupled.add('spatialbeam',
            SpatialBeamGroup(num_y, cons, E, G, stress, mrho),
            promotes=['*'])

coupled.nl_solver = Newton()
coupled.nl_solver.options['iprint'] = 1
coupled.nl_solver.line_search.options['iprint'] = 1
coupled.ln_solver = ScipyGMRES()
coupled.ln_solver.options['iprint'] = 1
coupled.ln_solver.preconditioner = LinearGaussSeidel()
coupled.weissinger.ln_solver = LinearGaussSeidel()
coupled.spatialbeam.ln_solver = LinearGaussSeidel()


coupled.nl_solver = NLGaussSeidel()   ### Uncomment this out to use NLGS

coupled.nl_solver.options['iprint'] = 1
coupled.nl_solver.options['atol'] = 1e-5
coupled.nl_solver.options['rtol'] = 1e-12
    
coupled.nl_solver = HybridGSNewton()   ### Uncomment this out to use Hybrid GS Newton
coupled.nl_solver.nlgs.options['iprint'] = 1
coupled.nl_solver.nlgs.options['maxiter'] = 5
coupled.nl_solver.newton.options['atol'] = 1e-7
coupled.nl_solver.newton.options['rtol'] = 1e-7
coupled.nl_solver.newton.options['iprint'] = 1


root.add('coupled',
         coupled,
         promotes=['*'])
root.add('fuelburn',
         FunctionalBreguetRange(W0, CT, a, R, M),
         promotes=['*'])
root.add('eq_con',
         FunctionalEquilibrium(W0),
         promotes=['*'])

prob = Problem()
prob.root = root
prob.print_all_convergence()

prob.driver = ScipyOptimizer()
prob.driver.options['optimizer'] = 'SLSQP'
prob.driver.options['disp'] = True
prob.driver.options['tol'] = 1.0e-3

prob.driver.add_desvar('twist',lower= -10.,
                       upper=10., scaler=1000)
prob.driver.add_desvar('alpha', lower=-10., upper=10., scaler=1000)
prob.driver.add_desvar('t',
                       lower= 0.003,
                       upper= 0.25, scaler=1000)
prob.driver.add_objective('fuelburn')
prob.driver.add_constraint('failure', upper=0.0)
prob.driver.add_constraint('eq_con', equals=0.0)

prob.driver.add_recorder(SqliteRecorder('aerostruct.db'))

prob.setup()

if len(sys.argv) == 1:
    st = time.time()
    prob.run_once()
    print "runtime: ", time.time() - st
elif sys.argv[1] == '0':
    prob.run_once()
    prob.check_partial_derivatives(compact_print=True)
elif sys.argv[1] == '1':
    prob.run()
