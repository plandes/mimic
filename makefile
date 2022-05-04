## makefile automates the build and deployment for python projects

## build config

# type of project
PROJ_TYPE =		python
PROJ_MODULES =		git python-resources python-cli python-doc python-doc-deploy
PY_DEP_POST_DEPS +=	modeldeps

include ./zenbuild/main.mk


.PHONY:			modeldeps
modeldeps:
			$(PIP_BIN) install $(PIP_ARGS) -r $(PY_SRC)/requirements-model.txt
