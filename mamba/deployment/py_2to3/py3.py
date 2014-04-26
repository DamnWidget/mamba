
# Copyright (c) 2012 Oscar Campos <oscar.campos@member.fsf.org>
# See LICENSE for more details

from mamba import plugin


class DeployerProvider(metaclass=plugin.ExtensionPoint):
    """
    Mount point for plugins which refer to Deployers for our applications.
    """
