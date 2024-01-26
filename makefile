## makefile automates the build and deployment for python projects

## Build config
#
# project definition
PROJ_TYPE =		python
PROJ_MODULES =		git python-resources python-cli python-doc python-doc-deploy

# build config
PY_DEP_POST_DEPS +=	modeldeps
ADD_CLEAN +=		feature.csv data
CLEAN_DEPS +=		example-clean
ADD_CLEAN_ALL +=	$(ADM_DIR)

# project
ADM_DIR =		adm

include ./zenbuild/main.mk


.PHONY:			modeldeps
modeldeps:
			$(PIP_BIN) install $(PIP_ARGS) \
				-r $(PY_SRC)/requirements-model.txt --no-deps

.PHONY:			postgresqldeps
postgresqldeps:
			$(PIP_BIN) install $(PIP_ARGS) \
				-r $(PY_SRC)/requirements-postgresql.txt --no-deps


.PHONY:			example-run
example-run:
			( cd example ; PYTHONPATH=$$PYTHONPATH:../src/python ./shownote.py parse )

.PHONY:			example-api-run
example-api-run:
			( cd example ; PYTHONPATH=$$PYTHONPATH:../src/python ./api.py )

.PHONY:			example-clean
example-clean:
			PYTHONPATH=src/python example/shownote.py clean

# test the MIMIC-III database (unavilable database in GitHub workflows)
.PHONY:			testdb
testdb:
			make PY_SRC_TEST=test/db test

.PHONY:			testadmexport
testadmexport:
			$(eval cor=363)
			make PY_CLI_ARGS="adm 100581 --format raw" pycli
			@cat $(ADM_DIR)/100581/4468--discharge-summary--report.txt | \
			  wc -l | xargs -i{} bash -c \
			  "if [ '{}' != '$(cor)' ] ; then echo {} != $(cor) ; exit 1 ; fi"
			@echo "success: line count output: $(cor)"
			rm -r $(ADM_DIR)

# todo: 
.PHONY:			testall
testall:		test testadmexport
