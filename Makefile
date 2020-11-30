GCP_PROJECT_ID=adventures-michaelfbryan-com
ENV=default

define get-secret
$(shell gcloud secrets versions access latest --secret=$(1) --project=$(GCP_PROJECT_ID))
endef

create-tf-backend-bucket:
	gsutil mb -p ${GCP_PROJECT_ID} gs://terraform.adventures.michaelfbryan.com

terraform-create-workspace:
	cd terraform && terraform workspace new ${ENV}

terraform-init:
	cd terraform && \
		terraform workspace select ${ENV} && \
		terraform init

define terraform-action
	cd terraform && \
		terraform workspace select ${ENV} && \
		terraform ${1} \
			-var-file="./common.tfvars"  \
			-var="do_token=${call get-secret,digital_ocean_token}"
endef

plan:
	$(call terraform-action,plan)

apply:
	$(call terraform-action,apply)
