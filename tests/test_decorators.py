"""Tests for the decorators module."""

from groundhog_hpc.decorators import function, method
from groundhog_hpc.function import Function, Method


class TestFunctionDecorator:
    """Test the @hog.function decorator."""

    def test_creates_function_wrapper(self):
        """Test that decorator creates a Function instance."""

        @function()
        def my_function():
            return "result"

        assert isinstance(my_function, Function)

    def test_uses_default_config_when_no_args(self):
        """Test that decorator config is empty when no arguments provided."""

        @function()
        def my_function():
            return "result"

        # ConfigResolver will handle merging DEFAULT_USER_CONFIG at call-time
        assert my_function.default_user_endpoint_config == {}

    def test_accepts_endpoint_parameter(self, mock_endpoint_uuid):
        """Test that endpoint parameter is accepted."""

        @function(endpoint=mock_endpoint_uuid)
        def my_function():
            return "result"

        assert my_function.endpoint == mock_endpoint_uuid

    def test_accepts_walltime_parameter(self):
        """Test that walltime parameter is accepted and added to config."""

        @function(walltime=60)
        def my_function():
            return "result"

        # Walltime should be in config, not the walltime attribute (escape hatch)
        assert my_function.default_user_endpoint_config["walltime"] == 60
        assert my_function.walltime is None

    def test_accepts_custom_endpoint_config(self):
        """Test that custom endpoint configuration is accepted."""

        @function(account="my_account", cores_per_node=4)
        def my_function():
            return "result"

        assert "account" in my_function.default_user_endpoint_config
        assert my_function.default_user_endpoint_config["account"] == "my_account"
        assert my_function.default_user_endpoint_config["cores_per_node"] == 4

    def test_merges_worker_init_with_default(self):
        """Test that custom worker_init is stored in decorator config."""
        custom_init = "module load custom"

        @function(worker_init=custom_init)
        def my_function():
            return "result"

        # Decorator should only have custom init, ConfigResolver will merge with DEFAULT
        assert my_function.default_user_endpoint_config["worker_init"] == custom_init


class TestMethodDecorator:
    """Test the @hog.method decorator."""

    def test_creates_method_wrapper(self):
        """Test that decorator creates a Method instance."""

        @method()
        def my_method():
            return "result"

        assert isinstance(my_method, Method)

    def test_accepts_endpoint_parameter(self, mock_endpoint_uuid):
        """Test that endpoint parameter is accepted."""

        @method(endpoint=mock_endpoint_uuid)
        def my_method():
            return "result"

        assert my_method.endpoint == mock_endpoint_uuid

    def test_works_as_class_method(self):
        """Test that decorator works when applied to class method."""

        class MyClass:
            @method()
            def compute(x):  # No self - staticmethod semantics
                return x * 2

        # Should be accessible via class and instance
        assert isinstance(MyClass.compute, Method)
        assert isinstance(MyClass().compute, Method)
        assert MyClass.compute(5) == 10
        assert MyClass().compute(5) == 10

    def test_warns_when_first_param_is_self(self, caplog):
        """Test that a warning is logged when first parameter is named 'self'."""
        import logging

        with caplog.at_level(logging.WARNING, logger="groundhog_hpc"):

            @method()
            def compute(self, x):
                return x * 2

        assert any(
            "'self'" in record.message and "staticmethod" in record.message
            for record in caplog.records
        )

    def test_warns_when_first_param_is_cls(self, caplog):
        """Test that a warning is logged when first parameter is named 'cls'."""
        import logging

        with caplog.at_level(logging.WARNING, logger="groundhog_hpc"):

            @method()
            def compute(cls, x):
                return x * 2

        assert any(
            "'cls'" in record.message and "staticmethod" in record.message
            for record in caplog.records
        )

    def test_no_warning_when_first_param_is_not_self_or_cls(self, caplog):
        """Test that no warning is logged when first parameter is not 'self' or 'cls'."""
        import logging

        with caplog.at_level(logging.WARNING):

            @method()
            def compute(data, x):
                return data + x

        assert len(caplog.records) == 0
        # Should not raise any warnings
        assert isinstance(compute, Method)
