import openai
from openai import OpenAI
from dataextractai.utils.config import PARSER_OUTPUT_PATHS, ASSISTANT_CONFIG


# Define the path to the CSV file
OUTPUT_PATH_CSV = PARSER_OUTPUT_PATHS["consolidated_core"]["csv"]

from openai import OpenAI

client = OpenAI()


def upload_file_to_openai(file_path):
    with open(file_path, "rb") as file:
        response = openai.files.create(file=file, purpose="assistants")
        return response


# Function to list files attached to assistants and check for our file_id
def check_files_attached_to_assistants(file_id_to_check):
    for assistant_name, config in ASSISTANT_CONFIG.items():
        assistant_id = config["id"]

        # Retrieve the files attached to the assistant without pagination handling
        assistant_files_response = client.beta.assistants.files.list(
            assistant_id=assistant_id
        )

        # Access the data attribute from the response
        attached_files = assistant_files_response.data

        # Check if our file_id is in the attached files
        is_attached = any(
            file_obj.id == file_id_to_check for file_obj in attached_files
        )

        # Print details of each file
        for file_obj in attached_files:
            print(
                f"Assistant {assistant_name} has file ID: {file_obj.id}, created at: {file_obj.created_at}"
            )

        # Output the result for the specific file ID
        if is_attached:
            print(f"Verified File {file_id_to_check} is attached to {assistant_name}.")
        else:
            print(f"File {file_id_to_check} is NOT attached to {assistant_name}.")


# # Use this for uplaoding:
# upload_response = upload_file_to_openai(OUTPUT_PATH_CSV)
# print(upload_response)

# file_id = upload_response.id

# assistant_file = client.beta.assistants.files.create(
#     assistant_id=assistant_id, file_id=file_id
# )
# print(assistant_file)


# Function to attach the file to assistants
# This seems buggy even using the UI so not reliable currently
def attach_file_to_assistants(file_id, assistant_config):
    for assistant_name, config in assistant_config.items():
        assistant_id = config["id"]
        print(f"Attaching {file_id} to: {assistant_id}")
        client.beta.assistants.files.create(assistant_id=assistant_id, file_id=file_id)
        # print(f"Created {file_id} attachment to {assistant_name}")


# assistant_files = client.beta.assistants.files.list(
#     assistant_id="asst_gD4jt79G1dN8bsVxZq7j3eBj"
# )
# print(f"ASS test: {assistant_files}")


# Upload the CSV and get the file ID
# file_id = upload_file_to_openai(OUTPUT_PATH_CSV)
# print(f"File ID created on OpenID: {file_id}")

# File ID created on OpenID: FileObject(id='file-58LlABUb6psQaBwbXS2d4OSN', bytes=245780, created_at=1699493705, filename='consolidated_core_output.csv', object='file', purpose='assistants', status='processed', status_details=None)
file_id = "file-58LlABUb6psQaBwbXS2d4OSN"

# # Attach the file to the assistants
attach_file_to_assistants(file_id, ASSISTANT_CONFIG)

# # Verify file is attached to assistants
check_files_attached_to_assistants(file_id)


# The error message indicates that the object assistant_files which is expected to be a subscriptable dictionary-like object is actually an instance of SyncCursorPage[AssistantFile] and not directly subscriptable.

# This seems to be an issue with how the API's response is being handled. The SyncCursorPage[AssistantFile] is a special object that OpenAI uses to handle pagination. To access the data within it, you usually need to iterate over it or convert it into a list.
