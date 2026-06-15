"""Deploy orchestration for serverless-data-mesh."""

from serverless_data_mesh.deploy.runner import deploy_mesh, result_to_dict

__all__ = ["deploy_mesh", "result_to_dict"]
