## makefile automates the build and deployment for python projects

## build config

# type of project
PROJ_TYPE =		python
PROJ_MODULES =		git python-resources python-cli python-doc python-doc-deploy
PY_DEP_POST_DEPS +=	modeldeps
ADD_CLEAN +=		feature.csv data
CLEAN_DEPS +=		example-clean


include ./zenbuild/main.mk


.PHONY:			modeldeps
modeldeps:
			$(PIP_BIN) install $(PIP_ARGS) -r $(PY_SRC)/requirements-model.txt

.PHONY:			example-clean
example-clean:
			example/shownote.py clean

.PHONY:			testall
testall:		test
			@echo "should be 7848 lines"
			./mimic discharge --hadmid 100581 | wc -l
			./mimic discharge --hadmid 100581 | wc -l
