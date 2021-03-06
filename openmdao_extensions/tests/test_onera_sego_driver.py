import os
import unittest
import numpy as np
from math import cos, sin, pi
from openmdao.api import (
    IndepVarComp,
    Problem,
    Group,
    SqliteRecorder,
    CaseReader,
    ExplicitComponent,
)
from openmdao.test_suite.components.sellar_feature import SellarMDA
from openmdao_extensions.onera_sego_driver import OneraSegoDriver
from openmdao_extensions.onera_sego_driver import ONERASEGO_NOT_INSTALLED


class Branin(ExplicitComponent):
    def setup(self):
        self.add_input("x1", val=1.0)
        self.add_input("x2", val=1.0)
        self.add_output("obj", val=1.0)
        self.add_output("con", val=1.0)

    @staticmethod
    def compute(inputs, outputs):
        x_1 = inputs["x1"][0]
        x_2 = inputs["x2"][0]
        # obj
        part1 = (x_2 - (5.1 * x_1 ** 2) / (4.0 * pi ** 2) + 5.0 * x_1 / pi - 6.0) ** 2
        part2 = 10.0 * ((1.0 - 1.0 / (8.0 * pi)) * cos(x_1) + 1.0)
        part3 = (5.0 * x_1 + 25.0) / 15.0
        outputs["obj"] = part1 + part2 + part3

        # con
        x_g1 = (x_1 - 2.5) / 7.5
        x_g2 = (x_2 - 7.5) / 7.5
        part1 = (4.0 - 2.1 * x_g1 ** 2 + (x_g1 ** 4) / 3.0) * x_g1 ** 2
        part2 = x_g1 * x_g2
        part3 = (4.0 * x_g2 ** 2 - 4.0) * x_g2 ** 2
        part4 = 3.0 * sin(6.0 * (1.0 - x_g1))
        part5 = 3.0 * sin(6.0 * (1.0 - x_g2))
        outputs["con"] = -(part1 + part2 + part3 + part4 + part5 - 6.0)


class BraninMDA(Group):
    def setup(self):
        indeps = self.add_subsystem("indeps", IndepVarComp(), promotes=["*"])
        indeps.add_output("x1", 9.1)
        indeps.add_output("x2", 4.75)

        self.add_subsystem("Branin", Branin(), promotes=["*"])


class Ackley(ExplicitComponent):
    def setup(self):
        self.add_input("x", val=[1.0, 1.0])
        self.add_output("obj", val=1.0)

    @staticmethod
    def compute(inputs, outputs):
        dim = 2
        a = 20.0
        b = 0.2
        c = 2 * np.pi
        point = inputs["x"]
        outputs["obj"] = (
            -a * np.exp(-b * np.sqrt(1.0 / dim * np.sum(point ** 2)))
            - np.exp(1.0 / dim * np.sum(np.cos(c * point)))
            + a
            + np.exp(1)
        )


class AckleyMDA(Group):
    def setup(self):
        indeps = self.add_subsystem("indeps", IndepVarComp(), promotes=["*"])
        indeps.add_output("x", [1.0, 1.0])

        self.add_subsystem("Ackley", Ackley(), promotes=["*"])


class TestSegoMoe(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass  # os.remove(self.case_recorder_filename)

    @unittest.skipIf(ONERASEGO_NOT_INSTALLED, "SEGOMOE is not installed")
    def test_sellar(self):
        self.pb = pb = Problem(SellarMDA())
        pb.model.add_design_var("x", lower=0, upper=10)
        pb.model.add_design_var("z", lower=0, upper=10)
        pb.model.add_objective("obj")
        pb.model.add_constraint("con1", upper=0)
        pb.model.add_constraint("con2", upper=0)
        pb.driver = OneraSegoDriver(optimizer="SEGOMOE")
        pb.driver.opt_settings["maxiter"] = 10
        self.case_recorder_filename = "test_segomoe_driver_sellar.sqlite"
        recorder = SqliteRecorder(self.case_recorder_filename)
        pb.model.add_recorder(recorder)
        pb.setup()
        self.pb.run_driver()
        self.assertTrue(os.path.exists(self.case_recorder_filename))
        reader = CaseReader(self.case_recorder_filename)
        for case_id in reader.list_cases():
            case = reader.get_case(case_id)
            print(case.outputs["obj"])

    @unittest.skipIf(ONERASEGO_NOT_INSTALLED, "SEGOMOE is not installed")
    def test_branin(self):
        self.pb = pb = Problem(BraninMDA())
        pb.model.add_design_var("x1", lower=-5, upper=10)
        pb.model.add_design_var("x2", lower=0, upper=15)
        pb.model.add_objective("obj")
        pb.model.add_constraint("con", upper=0)
        self.case_recorder_filename = "test_segomoe_driver_branin.sqlite"
        self._check_recorder_file(pb, cstr=True, filename=self.case_recorder_filename)

    @unittest.skipIf(ONERASEGO_NOT_INSTALLED, "SEGOMOE is not installed")
    def test_ackley(self):
        self.pb = pb = Problem(AckleyMDA())
        pb.model.add_design_var("x", lower=-32.768, upper=32.768)
        pb.model.add_objective("obj")
        self.case_recorder_filename = "test_segomoe_driver_ackley.sqlite"
        self._check_recorder_file(pb, cstr=False, filename=self.case_recorder_filename)

    def _check_recorder_file(self, pb, cstr, filename):
        pb.driver = OneraSegoDriver()
        pb.driver.options["optimizer"] = "SEGOMOE"
        pb.driver.opt_settings["maxiter"] = 10
        # default model
        n_var = 2
        mod_obj = {
            "type": "Krig",
            "corr": "squared_exponential",
            "regr": "constant",
            "theta0": [1.0] * n_var,
            "thetaL": [0.1] * n_var,
            "thetaU": [10.0] * n_var,
            "normalize": True,
        }
        model_type = {"obj": mod_obj}
        if cstr:
            model_type["con"] = mod_obj
        pb.driver.opt_settings["model_type"] = model_type
        recorder = SqliteRecorder(self.case_recorder_filename)
        pb.model.add_recorder(recorder)
        pb.setup()
        self.pb.run_driver()
        self.assertTrue(os.path.exists(self.case_recorder_filename))
        reader = CaseReader(self.case_recorder_filename)
        for case_id in reader.list_cases():
            case = reader.get_case(case_id)
            print(case.outputs["obj"])


if __name__ == "__main__":
    unittest.main()
