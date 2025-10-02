"""Tests for the decorators module."""

from groundhog_hpc.decorators import function
from groundhog_hpc.function import Function
from groundhog_hpc.settings import DEFAULT_USER_CONFIG


class TestFunctionDecorator:
    """Test the @hog.function decorator."""

    def test_creates_function_wrapper(self):
        """Test that decorator creates a Function instance."""

        @function()
        def my_function():
            return "result"

        assert isinstance(my_function, Function)

    def test_uses_default_config_when_no_args(self):
        """Test that default config is used when no arguments provided."""

        @function()
        def my_function():
            return "result"

        assert my_function.user_endpoint_config == DEFAULT_USER_CONFIG

    def test_accepts_endpoint_parameter(self, mock_endpoint_uuid):
        """Test that endpoint parameter is accepted."""

        @function(endpoint=mock_endpoint_uuid)
        def my_function():
            return "result"

        assert my_function.endpoint == mock_endpoint_uuid

    def test_accepts_walltime_parameter(self):
        """Test that walltime parameter is accepted."""

        @function(walltime=60)
        def my_function():
            return "result"

        assert my_function.walltime == 60

    def test_accepts_custom_endpoint_config(self):
        """Test that custom endpoint configuration is accepted."""

        @function(account="my_account", cores_per_node=4)
        def my_function():
            return "result"

        assert "account" in my_function.user_endpoint_config
        assert my_function.user_endpoint_config["account"] == "my_account"
        assert my_function.user_endpoint_config["cores_per_node"] == 4

    def test_merges_worker_init_with_default(self):
        """Test that custom worker_init is merged with default."""
        custom_init = "module load custom"

        @function(worker_init=custom_init)
        def my_function():
            return "result"

        # Should contain both custom and default worker_init
        assert custom_init in my_function.user_endpoint_config["worker_init"]
        assert (
            DEFAULT_USER_CONFIG["worker_init"]
            in my_function.user_endpoint_config["worker_init"]
        )
