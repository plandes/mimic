#@meta {desc: "Python build configuration", date: "2025-06-23"}


## Build config
#
# project definition
PROJ_TYPE =		python
PROJ_MODULES =		python/doc python/package python/deploy
PY_TEST_TARGETS =	testcur
PY_TEST_ALL_TARGETS +=	testadmexport testdb
PY_CLEAN_DIRS +=	example
ADD_CLEAN +=		feature.csv data
CLEAN_ALL_DEPS +=	example-clean
ADD_CLEAN_ALL +=	$(ADM_DIR)

## Project
#
ADM_DIR =		adm


## Includes
#
include ./zenbuild/main.mk


## Targets
#
# retrieve, parse and show a note
.PHONY:			example-run
example-run:
			@$(MAKE) $(PY_MAKE_ARGS) pytestrun \
				ARG="( cd example ; ./shownote.py parse ) "

# use the mimic library API
.PHONY:			example-api-run
example-api-run:
			@$(MAKE) $(PY_MAKE_ARGS) pytestrun \
				ARG="( cd example ; ./api.py ) "

# clean the examples directory
.PHONY:			example-clean
example-clean:
			@$(MAKE) $(PY_MAKE_ARGS) pytestrun \
				ARG="( cd example ; ./shownote.py clean )"

# test the MIMIC-III database (unavilable database in GitHub workflows)
.PHONY:			testdb
testdb:
			@echo "test db"
			make PY_TEST_GLOB=db_test_*.py testcur

# export admission notes and check output line length
.PHONY:			testadmexport
testadmexport:
			@echo "testing admission export"
			$(eval cor=363)
			@$(MAKE) $(PY_MAKE_ARGS) pytestrun \
				ARG="./harness.py adm 100581 --format raw" > /dev/null 2>&1
			@cat $(ADM_DIR)/100581/4468--discharge-summary--report.txt | \
			  wc -l | xargs -i{} bash -c \
			  "if [ '{}' != '$(cor)' ] ; then echo {} != $(cor) ; exit 1 ; fi"
			@rm -r $(ADM_DIR)
			@echo "testing admission export...ok"
