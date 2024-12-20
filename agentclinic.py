import argparse
import anthropic
from transformers import pipeline
import openai, re, random, time, json, replicate, os
from openai import OpenAI
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
from accelerate import init_empty_weights, infer_auto_device_map
from accelerate import load_checkpoint_and_dispatch
#import deepspeed
import torch.distributed as dist

llama2_url = "meta/llama-2-70b-chat"
llama3_url = "meta/meta-llama-3-70b-instruct"
mixtral_url = "mistralai/mixtral-8x7b-instruct-v0.1"

# def setup_distributed():
#     # For torch.distributed.launch or torchrun
#     if 'RANK' in os.environ and 'WORLD_SIZE' in os.environ:
#         rank = int(os.environ['RANK'])
#         world_size = int(os.environ['WORLD_SIZE'])
#         dist.init_process_group(backend='nccl', rank=rank, world_size=world_size)
#     else:
#         # For single-node multi-GPU
#         dist.init_process_group(backend='nccl')
#         rank = dist.get_rank()
#         world_size = dist.get_world_size()
#     return rank, world_size

def setup_distributed():
    if not dist.is_initialized():
        dist.init_process_group(backend='nccl')
    rank = dist.get_rank()
    world_size = dist.get_world_size()
    torch.cuda.set_device(rank) 
    return rank, world_size


def load_huggingface_model(model_name):
    pipe = pipeline("text-generation", model=model_name, device_map="auto")
    return pipe

def inference_huggingface(prompt, pipe):
    response = pipe(prompt, max_new_tokens=100)[0]["generated_text"]
    response = response.replace(prompt, "")
    return response


def query_model(model_str, prompt, system_prompt, tries=30, timeout=20.0, image_requested=False, scene=None, max_prompt_len=2**14, clip_prompt=False):
    if model_str not in ["gpt4", "gpt3.5", "gpt4o", 'llama-2-70b-chat', "mixtral-8x7b", "gpt-4o-mini", "llama-3-70b-instruct", "gpt4v", "claude3.5sonnet", "o1-preview", "llama-3-70b-meditron"] and "_HF" not in model_str:
        raise Exception("No model by the name {}".format(model_str))
    for _ in range(tries):
        if clip_prompt: prompt = prompt[:max_prompt_len]
        #try:
        if image_requested:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", 
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url",
                        "image_url": {
                            "url": "{}".format(scene.image_url),
                        },
                    },
                ]},]
            if model_str == "gpt4v":
                response = openai.ChatCompletion.create(
                        model="gpt-4-vision-preview",
                        messages=messages,
                        temperature=0.05,
                        max_tokens=200,
                    )
            elif model_str == "gpt-4o-mini":
                response = openai.ChatCompletion.create(
                        model="gpt-4o-mini",
                        messages=messages,
                        temperature=0.05,
                        max_tokens=200,
                    )
            elif model_str == "gpt4":
                response = openai.ChatCompletion.create(
                        model="gpt-4-turbo",
                        messages=messages,
                        temperature=0.05,
                        max_tokens=200,
                    )
            elif model_str == "gpt4o":
                response = openai.ChatCompletion.create(
                        model="gpt-4o",
                        messages=messages,
                        temperature=0.05,
                        max_tokens=200,
                    )
            answer = response["choices"][0]["message"]["content"]
        if model_str == "gpt4":
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}]
            client = OpenAI(api_key="")
            chat_completion = client.chat.completions.create(model="gpt-4-turbo-preview", messages=messages,
                    temperature=0.05,
                    max_tokens=200,)
            answer = chat_completion.choices[0].message.content
            answer = re.sub("\s+", " ", answer)
        elif model_str == "gpt4v":
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}]
            response = openai.ChatCompletion.create(
                    model="gpt-4-vision-preview",
                    messages=messages,
                    temperature=0.05,
                    max_tokens=200,
                )
            answer = response["choices"][0]["message"]["content"]
            answer = re.sub("\s+", " ", answer)
        elif model_str == "gpt-4o-mini":
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}]
            response = openai.ChatCompletion.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.05,
                    max_tokens=200,
                )
            answer = response["choices"][0]["message"]["content"]
            answer = re.sub("\s+", " ", answer)
        elif model_str == "o1-preview":
            messages = [
                {"role": "user", "content": system_prompt + prompt}]
            response = openai.ChatCompletion.create(
                    model="o1-preview-2024-09-12",
                    messages=messages,
                )
            answer = response["choices"][0]["message"]["content"]
            answer = re.sub("\s+", " ", answer)
        elif model_str == "gpt3.5":
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}]
            response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    temperature=0.05,
                    max_tokens=200,
                )
            answer = response["choices"][0]["message"]["content"]
            answer = re.sub("\s+", " ", answer)
        elif model_str == "claude3.5sonnet":
            client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
            message = client.messages.create(
                model="claude-3-5-sonnet-20240620",
                system=system_prompt,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}])
            answer = json.loads(message.to_json())["content"][0]["text"]
        elif model_str == "gpt4o":
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}]

            client = OpenAI(api_key="")
            chat_completion = client.chat.completions.create(model="gpt-4o", messages=messages,
                    temperature=0.05,
                    max_tokens=200,)
            answer = chat_completion.choices[0].message.content
            answer = re.sub("\s+", " ", answer)
            # response = openai.ChatCompletion.create(
            #         model="gpt-4o",
            #         messages=messages,
            #         temperature=0.05,
            #         max_tokens=200,
            #     )
            # answer = response["choices"][0]["message"]["content"]
            # answer = re.sub("\s+", " ", answer)
        elif model_str == 'llama-2-70b-chat':
            output = replicate.run(
                llama2_url, input={
                    "prompt":  prompt, 
                    "system_prompt": system_prompt,
                    "max_new_tokens": 200})
            answer = ''.join(output)
            answer = re.sub("\s+", " ", answer)
        elif model_str == 'mixtral-8x7b':
            output = replicate.run(
                mixtral_url, 
                input={"prompt": prompt, 
                        "system_prompt": system_prompt,
                        "max_new_tokens": 75})
            answer = ''.join(output)
            answer = re.sub("\s+", " ", answer)
        elif model_str == 'llama-3-70b-instruct':
            output = replicate.run(
                llama3_url, input={
                    "prompt":  prompt, 
                    "system_prompt": system_prompt,
                    "max_new_tokens": 200})
            answer = ''.join(output)
            answer = re.sub("\s+", " ", answer)
        elif model_str == "llama-3-70b-meditron":
            # client = OpenAI(base_url="http://104.171.203.227:8000/v1", api_key="EMPTY")
            # # default values
            # temperature = 0.6
            # max_tokens = 1024
            # top_p = 0.9
            # messages = [
            #     {"role": "system", "content": system_prompt},
            #     {"role": "user", "content": prompt}]
            # #print(messages)

            # response = client.chat.completions.create(model="llama-3-70b-meditron", messages=messages, temperature=temperature, top_p=top_p, max_tokens=max_tokens)
            # answer = response.choices[0].message.content
            model_path = "/mloscratch/homes/bbernath/meditron_instruct"
            #rank, world_size = setup_distributed()
            # with init_empty_weights():
            #     #model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-3.1-70B-Instruct")
            #     model = AutoModelForCausalLM.from_pretrained(model_path)
            # device_map = infer_auto_device_map(
            #     model,
            #     max_memory={0: "75GB", 1: "75GB", 2: "75GB", 3: "75GB"},
            #     no_split_module_classes=["LlamaDecoderLayer"]
            # )
            # model.gradient_checkpointing_enable()
            # model = load_checkpoint_and_dispatch(
            #     model,
            #     model_path,
            #     device_map=device_map,
            #     no_split_module_classes=["LlamaDecoderLayer"]
            # )
            # tokenizer = AutoTokenizer.from_pretrained(model_path)
            # messages = [
            #     {"role": "system", "content": system_prompt},
            #     {"role": "user", "content": prompt}
            # ]
            # input_message = tokenizer.apply_chat_template(messages, tokenize=False)
            # tokenized_input = tokenizer(input_message, return_tensors="pt")
            # input_ids = tokenized_input["input_ids"]
            # # Set use_cache=False to avoid device mismatch errors
            # outputs = model.generate(
            #     input_ids=input_ids,
            #     max_length=1024,
            #     temperature=0.6,
            #     top_p=0.9,
            #     num_return_sequences=1,
            #     use_cache=False  # Important when using sharded models
            # )

            # answer = tokenizer.decode(outputs[0], skip_special_tokens=True)
            # print(answer)



            # Load model with DeepSpeed inference engine
            # model = deepspeed.init_inference(
            #     model,
            #     dtype=torch.float16,  # or torch.bfloat16 if supported
            #     tensor_parallel={"tp_size": world_size},  # Number of GPUs
            # )


            # # Load tokenizer and prepare input
            # tokenizer = AutoTokenizer.from_pretrained(model_path)
            # messages = [
            #     {"role": "system", "content": system_prompt},
            #     {"role": "user", "content": prompt}
            # ]
            # input_message = tokenizer.apply_chat_template(messages, tokenize=False)
            # tokenized_input = tokenizer(input_message, return_tensors="pt")
            # input_ids = tokenized_input["input_ids"]
            # device = torch.device(f'cuda:{rank}')
            # input_ids = input_ids.to(device)

            # # Keep input_ids on CPU

            # # Perform inference
            # outputs = model.generate(
            #     input_ids,
            #     max_length=1024,
            #     temperature=0.6,
            #     top_p=0.9,
            #     num_return_sequences=1
            # )
            # if rank == 0:
            #     answer = tokenizer.decode(outputs[0], skip_special_tokens=True)
            #     print(answer)
            # else:
            #     answer = None
            #     print("------------------------------------------not rank 0--------------------------------------")

            # Decode and print the response
            # response = tokenizer.decode(outputs[0], skip_special_tokens=True)
            # print(response)
            with init_empty_weights():
                model = AutoModelForCausalLM.from_pretrained(model_path)

            # Automatically infer how to split the model across two GPUs
            device_map = infer_auto_device_map(model, max_memory={0: "80GB", 1: "80GB", 2: "80GB", 3: "80GB"}, no_split_module_classes=["LlamaDecoderLayer"])

            # Load model with the device map
            model.gradient_checkpointing_enable()
            model = load_checkpoint_and_dispatch(model, model_path, device_map=device_map)

            tokenizer = AutoTokenizer.from_pretrained(model_path)
            messages = [{"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}]
            input_message = tokenizer.apply_chat_template(messages, tokenize = False)
            tokenized_input = tokenizer(input_message, return_tensors="pt")
            input_ids = tokenized_input["input_ids"]
            #embedding_device = model.get_submodule('model.embed_tokens').weight.device

            # Move input_ids to the correct device
            #input_ids = input_ids.to(embedding_device)

            # Perform inference
            outputs = model.generate(input_ids, max_length=4096, temperature=0.6, top_p=0.9, num_return_sequences=1)
            #tokenized_input = torch.tensor(tokenizer.apply_chat_template(messages)).unsqueeze(0).to("cuda")
            #output = model.generate(input_ids, max_length=1024, do_sample=True, temperature=0.6, top_p=0.9, num_return_sequences=1)#model.generate(tokenized_input, max_length=1024, do_sample=True, temperature=0.6, top_p=0.9, num_return_sequences=1)
            generated_tokens = outputs[0][len(input_ids[0]):]  # Slice off the input part from the output

            # Decode only the generated portion of the sequence
            answer = tokenizer.decode(generated_tokens, skip_special_tokens=True)
            #answer = tokenizer.decode(outputs[0], skip_special_tokens=True).replace(input_message, "")
            print("------------------------------------------answer--------------------------------------")
            print(answer)

        elif "HF_" in model_str:
            input_text = system_prompt + prompt 
            #if self.pipe is None:
            #    self.pipe = load_huggingface_model(self.backend.replace("HF_", ""))
            raise Exception("Sorry, fixing TODO :3") #inference_huggingface(input_text, self.pipe)
        return answer
        
        # except Exception as e:
        #     print("Error: ", e)
        #     #time.sleep(timeout)
        #     continue
    raise Exception("Max retries: timeout")



class ScenarioMedQA:
    def __init__(self, scenario_dict) -> None:
        self.scenario_dict = scenario_dict
        self.tests = scenario_dict["OSCE_Examination"]["Test_Results"]
        self.diagnosis = scenario_dict["OSCE_Examination"]["Correct_Diagnosis"]
        self.patient_info  = scenario_dict["OSCE_Examination"]["Patient_Actor"]
        self.examiner_info  = scenario_dict["OSCE_Examination"]["Objective_for_Doctor"]
        self.physical_exams = scenario_dict["OSCE_Examination"]["Physical_Examination_Findings"]
    
    def patient_information(self) -> dict:
        return self.patient_info

    def examiner_information(self) -> dict:
        return self.examiner_info
    
    def exam_information(self) -> dict:
        exams = self.physical_exams
        exams["tests"] = self.tests
        return exams
    
    def diagnosis_information(self) -> dict:
        return self.diagnosis


class ScenarioLoaderMedQA:
    def __init__(self) -> None:
        with open("agentclinic_medqa.jsonl", "r") as f:
            self.scenario_strs = [json.loads(line) for line in f]
        self.scenarios = [ScenarioMedQA(_str) for _str in self.scenario_strs]
        self.num_scenarios = len(self.scenarios)
    
    def sample_scenario(self):
        return self.scenarios[random.randint(0, len(self.scenarios)-1)]
    
    def get_scenario(self, id):
        if id is None: return self.sample_scenario()
        return self.scenarios[id]
        


class ScenarioMedQAExtended:
    def __init__(self, scenario_dict) -> None:
        self.scenario_dict = scenario_dict
        self.tests = scenario_dict["OSCE_Examination"]["Test_Results"]
        self.diagnosis = scenario_dict["OSCE_Examination"]["Correct_Diagnosis"]
        self.patient_info  = scenario_dict["OSCE_Examination"]["Patient_Actor"]
        self.examiner_info  = scenario_dict["OSCE_Examination"]["Objective_for_Doctor"]
        self.physical_exams = scenario_dict["OSCE_Examination"]["Physical_Examination_Findings"]
    
    def patient_information(self) -> dict:
        return self.patient_info

    def examiner_information(self) -> dict:
        return self.examiner_info
    
    def exam_information(self) -> dict:
        exams = self.physical_exams
        exams["tests"] = self.tests
        return exams
    
    def diagnosis_information(self) -> dict:
        return self.diagnosis


class ScenarioLoaderMedQAExtended:
    def __init__(self) -> None:
        with open("agentclinic_medqa_extended.jsonl", "r") as f:
            self.scenario_strs = [json.loads(line) for line in f]
        self.scenarios = [ScenarioMedQAExtended(_str) for _str in self.scenario_strs]
        self.num_scenarios = len(self.scenarios)
    
    def sample_scenario(self):
        return self.scenarios[random.randint(0, len(self.scenarios)-1)]
    
    def get_scenario(self, id):
        if id is None: return self.sample_scenario()
        return self.scenarios[id]
        
class ScenarioHealthCareMagic:
    def __init__(self, scenario_dict) -> None:
        # Assuming similar structure to MedQA, adjust these if the structure differs
        self.scenario_dict = scenario_dict
        self.tests = scenario_dict["OSCE_Examination"]["Test_Results"]
        if "Correct_Diagnosis" in scenario_dict["OSCE_Examination"]:
            self.diagnosis = scenario_dict["OSCE_Examination"]["Correct_Diagnosis"]
        else:
            self.diagnosis = scenario_dict["Correct_Diagnosis"]
        self.patient_info = scenario_dict["OSCE_Examination"]["Patient_Actor"]
        self.examiner_info = scenario_dict["OSCE_Examination"]["Objective_for_Doctor"]
        self.physical_exams = scenario_dict["OSCE_Examination"]["Physical_Examination_Findings"]

    def patient_information(self) -> dict:
        return self.patient_info

    def examiner_information(self) -> dict:
        return self.examiner_info
    
    def exam_information(self) -> dict:
        exams = self.physical_exams
        exams["tests"] = self.tests
        return exams
    
    def diagnosis_information(self) -> dict:
        return self.diagnosis


class ScenarioLoaderHealthCareMagic:
    def __init__(self) -> None:
        with open("agentclinic_HealthCareMagic.json", "r") as f:
            self.scenario_strs = json.load(f)
        self.scenarios = [ScenarioHealthCareMagic(_str) for _str in self.scenario_strs]
        self.num_scenarios = len(self.scenarios)
    
    def sample_scenario(self):
        return self.scenarios[random.randint(0, len(self.scenarios)-1)]
    
    def get_scenario(self, id):
        if id is None: return self.sample_scenario()
        return self.scenarios[id]


class ScenarioMIMICIVQA:
    def __init__(self, scenario_dict) -> None:
        self.scenario_dict = scenario_dict
        self.tests = scenario_dict["OSCE_Examination"]["Test_Results"]
        self.diagnosis = scenario_dict["OSCE_Examination"]["Correct_Diagnosis"]
        self.patient_info  = scenario_dict["OSCE_Examination"]["Patient_Actor"]
        self.examiner_info  = scenario_dict["OSCE_Examination"]["Objective_for_Doctor"]
        self.physical_exams = scenario_dict["OSCE_Examination"]["Physical_Examination_Findings"]
    
    def patient_information(self) -> dict:
        return self.patient_info

    def examiner_information(self) -> dict:
        return self.examiner_info
    
    def exam_information(self) -> dict:
        exams = self.physical_exams
        exams["tests"] = self.tests
        return exams
    
    def diagnosis_information(self) -> dict:
        return self.diagnosis


class ScenarioLoaderMIMICIV:
    def __init__(self) -> None:
        with open("agentclinic_mimiciv.jsonl", "r") as f:
            self.scenario_strs = [json.loads(line) for line in f]
        self.scenarios = [ScenarioMIMICIVQA(_str) for _str in self.scenario_strs]
        self.num_scenarios = len(self.scenarios)
    
    def sample_scenario(self):
        return self.scenarios[random.randint(0, len(self.scenarios)-1)]
    
    def get_scenario(self, id):
        if id is None: return self.sample_scenario()
        return self.scenarios[id]


class ScenarioNEJMExtended:
    def __init__(self, scenario_dict) -> None:
        self.scenario_dict = scenario_dict 
        self.question = scenario_dict["question"] 
        self.image_url = scenario_dict["image_url"] 
        self.diagnosis = [_sd["text"] 
            for _sd in scenario_dict["answers"] if _sd["correct"]][0]
        self.patient_info = scenario_dict["patient_info"]
        self.physical_exams = scenario_dict["physical_exams"]

    def patient_information(self) -> str:
        patient_info = self.patient_info
        return patient_info

    def examiner_information(self) -> str:
        return "What is the most likely diagnosis?"
    
    def exam_information(self) -> str:
        exams = self.physical_exams
        return exams
    
    def diagnosis_information(self) -> str:
        return self.diagnosis


class ScenarioLoaderNEJMExtended:
    def __init__(self) -> None:
        with open("agentclinic_nejm_extended.jsonl", "r") as f:
            self.scenario_strs = [json.loads(line) for line in f]
        self.scenarios = [ScenarioNEJMExtended(_str) for _str in self.scenario_strs]
        self.num_scenarios = len(self.scenarios)
    
    def sample_scenario(self):
        return self.scenarios[random.randint(0, len(self.scenarios)-1)]
    
    def get_scenario(self, id):
        if id is None: return self.sample_scenario()
        return self.scenarios[id]


class ScenarioNEJM:
    def __init__(self, scenario_dict) -> None:
        self.scenario_dict = scenario_dict 
        self.question = scenario_dict["question"] 
        self.image_url = scenario_dict["image_url"] 
        self.diagnosis = [_sd["text"] 
            for _sd in scenario_dict["answers"] if _sd["correct"]][0]
        self.patient_info = scenario_dict["patient_info"]
        self.physical_exams = scenario_dict["physical_exams"]

    def patient_information(self) -> str:
        patient_info = self.patient_info
        return patient_info

    def examiner_information(self) -> str:
        return "What is the most likely diagnosis?"
    
    def exam_information(self) -> str:
        exams = self.physical_exams
        return exams
    
    def diagnosis_information(self) -> str:
        return self.diagnosis


class ScenarioLoaderNEJM:
    def __init__(self) -> None:
        with open("agentclinic_nejm.jsonl", "r") as f:
            self.scenario_strs = [json.loads(line) for line in f]
        self.scenarios = [ScenarioNEJM(_str) for _str in self.scenario_strs]
        self.num_scenarios = len(self.scenarios)
    
    def sample_scenario(self):
        return self.scenarios[random.randint(0, len(self.scenarios)-1)]
    
    def get_scenario(self, id):
        if id is None: return self.sample_scenario()
        return self.scenarios[id]


class PatientAgent:
    def __init__(self, scenario, backend_str="gpt4", bias_present=None, setting = "high") -> None:
        # disease of patient, or "correct answer"
        self.disease = ""
        # symptoms that patient presents
        self.symptoms = ""
        # conversation history between doctor and patient
        self.agent_hist = ""
        # language model backend for patient agent
        self.backend = backend_str
        # presentation of any form of bias
        self.bias_present = (None if bias_present == "None" else bias_present)
        # sample initial question from dataset
        self.scenario = scenario
        self.reset()
        self.pipe = None
        self.setting = setting

        self.biases = ["recency", "frequency", "false_consensus", "self_diagnosis", "gender", "race", "sexual_orientation", "cultural", "education", "religion", "socioeconomic"]

    def generate_bias(self) -> str:
        """ 
        ================
        Cognitive biases 
        ================
        """
        if self.bias_present == "recency":
            return "\nRecently, you had a friend with similar symptoms to yours that was diagnosed with cancer. This affects how you interact with the doctor.\n"
        elif self.bias_present == "frequency":
            return "\nYou recently learned that most frequently, doctors diagnose this as cancer based on past cases. This affects how you interact with the doctor.\n"
        elif self.bias_present == "false_consensus":
            return "\nMost of your friends who heard about your symptoms believe that you have cancer. This affects how you interact with the doctor.\n"
        elif self.bias_present == "self_diagnosis":
            return "\nYou recently performed a thorough investigation of your symptoms online and have come to the conclusion that you should be diagnosed with cancer. While the doctor may believe otherwise you remain convinced you have cancer. This affects how you interact with the doctor.\n"
        elif self.bias_present == "gender":
            return "\nYou are uncomfortable with your doctor because you find out that they are a particular gender and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "race":
            return "\nYou are uncomfortable with your doctor because you find out that they are a particular race and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "sexual_orientation":
            return "\nYou are uncomfortable with your doctor because you find out that they are a particular sexual orientation and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "cultural":
            return "\nYou are uncomfortable with your doctor because you find out that they are from a particular culture and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "education":
            return "\nYou are uncomfortable with your doctor because you find out that they went to a low ranked medical school and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "religion":
            return "\nYou are uncomfortable with your doctor because you find out that they believe in a particular religion and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "socioeconomic":
            return "\nYou are uncomfortable with your doctor because you find out that they are from a particular socioeconomic background and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present is None:
            pass
        else:
            print("BIAS TYPE {} NOT SUPPORTED, ignoring bias...".format(self.bias_present))
        return ""

    def inference_patient(self, question) -> str:
        answer = query_model(self.backend, "\nHere is a history of your dialogue: " + self.agent_hist + "\n Here was the doctor response: " + question + "Now please continue your dialogue\nPatient: ", self.system_prompt())
        self.agent_hist += question + "\n\n" + answer + "\n\n"
        return answer

    def system_prompt(self) -> str:
        bias_prompt = ""
        if self.bias_present is not None:
            bias_prompt = self.generate_bias()
        patient_setting = {"high":"", "low": "You live in a low ressource setting", "war": "You are in a war zone"}
        time_setting = ["You have plenty of time to discuss your symptoms with the doctor", "You have limited time to discuss your symptoms with the doctor"]
        eduction_background = ["You have a high level of education", "You have a low level of education"]
        trust = ["You trust the doctor", "You do not trust the doctor"]
        base = """You are a patient in a clinic who only responds in the form of dialogue. You are being inspected by a doctor who will ask you questions and will perform exams on you in order to understand your disease. Your answer will only be 1-3 sentences in length."""
        symptoms = "\n\nBelow is all of your information. {}. \n\n Remember, you must not reveal your disease explicitly but may only convey the symptoms you have in the form of dialogue if you are asked.".format(self.symptoms)
        return base + bias_prompt + symptoms
    
    def reset(self) -> None:
        self.agent_hist = ""
        self.symptoms = self.scenario.patient_information()

    def add_hist(self, hist_str) -> None:
        self.agent_hist += hist_str + "\n\n"


class DoctorAgent:
    def __init__(self, scenario, backend_str="gpt4", max_infs=20, bias_present=None, img_request=False, knows_diagnosis=False, correct_diagnosis="", number_of_sentences = "1-2", system_prompt = None, setting = "high") -> None:
        # number of inference calls to the doctor
        self.infs = 0
        # maximum number of inference calls to the doctor
        self.MAX_INFS = max_infs
        # conversation history between doctor and patient
        self.agent_hist = ""
        # presentation information for doctor
        self.presentation = ""
        # language model backend for doctor agent
        self.backend = backend_str
        # presentation of any form of bias
        self.bias_present = (None if bias_present == "None" else bias_present)
        # prepare initial conditions for LLM
        self.scenario = scenario
        self.reset()
        self.pipe = None
        self.knows_diagnosis = knows_diagnosis
        self.correct_diagnosis = correct_diagnosis
        self.img_request = img_request
        self.number_of_sentences = number_of_sentences
        self.setting = setting

        if system_prompt is None:
            setting_doctor = {"high":"high ressource setting, you have access to any equipment", "low":"low ressource setting, you shouldn't request any expensive tests unless necessary", "war":"war zone setting, try to make a diagnosis quickly and with minimal resources, be direct and empathetic"}
            self.base = "You are a doctor in a {}, you only responds in the form of dialogue. You are inspecting a patient who you will ask questions in order to understand their disease. You are only allowed to ask {} questions total before you must make a decision. You have asked {} questions so far. You can request test results using the format \"REQUEST TEST: [test]\". For example, \"REQUEST TEST: Chest_X-Ray\". Your dialogue will be {} sentences in length. Once you have decided to make a diagnosis please type \"DIAGNOSIS READY: [diagnosis here]\"".format(self.setting_doctor[self.setting], self.MAX_INFS, self.infs, self.number_of_sentences) + ("You may also request medical images related to the disease to be returned with \"REQUEST IMAGES\"." if self.img_request else "") + (f"You suspect that the patient suffers from {self.correct_diagnosis}. This affects the questions you ask the patient." if self.knows_diagnosis else "")" 
        else:
            self.base = system_prompt
        self.biases = ["recency", "frequency", "false_consensus", "confirmation", "status_quo", "gender", "race", "sexual_orientation", "cultural", "education", "religion", "socioeconomic"]

    def generate_bias(self) -> str:
        """ 
        ================
        Cognitive biases 
        ================
        """
        if self.bias_present == "recency":
            return "\nRecently, you learned that a doctor with similar symptoms to the patient that diagnosed their patient with cancer. This affects how you interact with the patient.\n"
        elif self.bias_present == "frequency":
            return "\nYou recently learned that most frequently, doctors diagnose patients with similar symptoms with cancer based on past cases. This affects how you interact with the patient.\n"
        elif self.bias_present == "false_consensus":
            return "\nMost of your colleagues who heard about the patient's symptoms believe that they have cancer. This affects how you interact with the patient.\n"
        elif self.bias_present == "status_quo":
            return "\nYour hosptial has been diagnosing these patient's symptoms with cancer for the past 10 years. This affects how you interact with the patient.\n"
        elif self.bias_present == "confirmation":
            return "\nYou are initially confident that the patient has cancer. This affects how you interact with the patient.\n"
        elif self.bias_present == "gender":
            return "\nYou are uncomfortable with your patient because you find out that they are a particular gender and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "race":
            return "\nYou are uncomfortable with your patient because you find out that they are a particular race and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "sexual_orientation":
            return "\nYou are uncomfortable with your patient because you find out that they are a particular sexual orientation and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "cultural":
            return "\nYou are uncomfortable with your patient because you find out that they are from a particular culture and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "education":
            return "\nYou are uncomfortable with your patient because you find out that they are uneducated and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "religion":
            return "\nYou are uncomfortable with your patient because you find out that they believe in a particular religion and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present == "socioeconomic":
            return "\nYou are uncomfortable with your patient because you find out that they are from a particular socioeconomic background and you do not trust their judgement. This affects how you interact with them.\n"
        elif self.bias_present is None:
            pass
        else:
            print("BIAS TYPE {} NOT SUPPORTED, ignoring bias...".format(self.bias_present))
        return ""

    def inference_doctor(self, question, image_requested=False) -> str:
        answer = str()
        if self.infs >= self.MAX_INFS: return "Maximum inferences reached"
        answer = query_model(self.backend, "\nHere is a history of your dialogue: " + self.agent_hist + "\n Here was the patient response: " + question + "Now please continue your dialogue\nDoctor: ", self.system_prompt(), image_requested=image_requested, scene=self.scenario)
        self.agent_hist += question + "\n\n" + answer + "\n\n"
        self.infs += 1
        return answer

    def system_prompt(self) -> str:
        bias_prompt = ""
        if self.bias_present is not None:
            bias_prompt = self.generate_bias()
        base = self.base 
        presentation = "\n\nBelow is all of the information you have. {}. \n\n Remember, you must discover their disease by asking them questions. You are also able to provide exams.".format(self.presentation)
        return base + bias_prompt + presentation

    def reset(self) -> None:
        self.agent_hist = ""
        self.presentation = self.scenario.examiner_information()


class MeasurementAgent:
    def __init__(self, scenario, backend_str="gpt4") -> None:
        # conversation history between doctor and patient
        self.agent_hist = ""
        # presentation information for measurement 
        self.presentation = ""
        # language model backend for measurement agent
        self.backend = backend_str
        # prepare initial conditions for LLM
        self.scenario = scenario
        self.pipe = None
        self.reset()

    def inference_measurement(self, question) -> str:
        answer = str()
        answer = query_model(self.backend, "\nHere is a history of the dialogue: " + self.agent_hist + "\n Here was the doctor measurement request: " + question, self.system_prompt())
        self.agent_hist += question + "\n\n" + answer + "\n\n"
        return answer

    def system_prompt(self) -> str:
        base = "You are an measurement reader who responds with medical test results. Please respond in the format \"RESULTS: [results here]\""
        presentation = "\n\nBelow is all of the information you have. {}. \n\n If the requested results are not in your data then you can respond with NORMAL READINGS.".format(self.information)
        return base + presentation
    
    def add_hist(self, hist_str) -> None:
        self.agent_hist += hist_str + "\n\n"

    def reset(self) -> None:
        self.agent_hist = ""
        self.information = self.scenario.exam_information()


def compare_results(diagnosis, correct_diagnosis, moderator_llm, mod_pipe):
    answer = query_model(moderator_llm, "\nHere is the correct diagnosis: " + correct_diagnosis + "\n Here was the doctor dialogue: " + diagnosis + "\nAre these the same?", "You are responsible for determining if the corrent diagnosis and the doctor diagnosis are the same disease. Please respond only with Yes or No. Nothing else.")
    return answer.lower()


def main(api_key, replicate_api_key, inf_type, doctor_bias, patient_bias, doctor_llm, patient_llm, measurement_llm, moderator_llm, num_scenarios, dataset, img_request, total_inferences, anthropic_api_key=None, number_of_sentences="1-2"):
    openai.api_key = api_key
    anthropic_llms = ["claude3.5sonnet"]
    replicate_llms = ["llama-3-70b-instruct", "llama-2-70b-chat", "mixtral-8x7b"]
    if patient_llm in replicate_llms or doctor_llm in replicate_llms:
        os.environ["REPLICATE_API_TOKEN"] = replicate_api_key
    if doctor_llm in anthropic_llms:
        os.environ["ANTHROPIC_API_KEY"] = anthropic_api_key

    # Load MedQA, MIMICIV or NEJM agent case scenarios
    if dataset == "MedQA":
        scenario_loader = ScenarioLoaderMedQA()
    elif dataset == "MedQA_Ext":
        scenario_loader = ScenarioLoaderMedQAExtended()
    elif dataset == "NEJM":
        scenario_loader = ScenarioLoaderNEJM()
    elif dataset == "NEJM_Ext":
        scenario_loader = ScenarioLoaderNEJMExtended()
    elif dataset == "MIMICIV":
        scenario_loader = ScenarioLoaderMIMICIV()
    elif dataset == "HealthCareMagic":
        scenario_loader = ScenarioLoaderHealthCareMagic()

    elif dataset == "new_patient":
        with open("generated_patient.jsonl", "r") as f:
            for line in f:
                scenario_dict = json.loads(line)
                
    else:
        raise Exception("Dataset {} does not exist".format(str(dataset)))
    total_correct = 0
    total_presents = 0
    setting = =["high", "low", "war"]

    # Pipeline for huggingface models
    if "HF_" in moderator_llm:
        pipe = load_huggingface_model(moderator_llm.replace("HF_", ""))
    else:
        pipe = None

    for _scenario_id in range(0, min(num_scenarios, scenario_loader.num_scenarios)):
        total_presents += 1
        pi_dialogue = str()
        # Initialize scenarios (MedQA/NEJM)
        scenario =  scenario_loader.get_scenario(id=_scenario_id)
        # Initialize agents
        meas_agent = MeasurementAgent(
            scenario=scenario,
            backend_str=measurement_llm)
        patient_agent = PatientAgent(
            scenario=scenario, 
            bias_present=patient_bias,
            backend_str=patient_llm)
        doctor_agent = DoctorAgent(
            scenario=scenario, 
            bias_present=doctor_bias,
            backend_str=doctor_llm,
            max_infs=total_inferences, 
            img_request=img_request,
            knows_diagnosis=True,
            correct_diagnosis=scenario.diagnosis_information(),
            number_of_sentences=number_of_sentences)

        doctor_dialogue = ""
        for _inf_id in range(total_inferences):
            # Check for medical image request
            if dataset == "NEJM":
                if img_request:
                    imgs = "REQUEST IMAGES" in doctor_dialogue
                else: imgs = True
            else: imgs = False
            # Check if final inference
            if _inf_id == total_inferences - 1:
                pi_dialogue += "This is the final question. Please provide a diagnosis.\n"
            # Obtain doctor dialogue (human or llm agent)
            if inf_type == "human_doctor":
                doctor_dialogue = input("\nQuestion for patient: ")
            else: 
                doctor_dialogue = doctor_agent.inference_doctor(pi_dialogue, image_requested=imgs)
            print("Doctor [{}%]:".format(int(((_inf_id+1)/total_inferences)*100)), doctor_dialogue)
            # Doctor has arrived at a diagnosis, check correctness
            if "DIAGNOSIS READY" in doctor_dialogue:
                correctness = compare_results(doctor_dialogue, scenario.diagnosis_information(), moderator_llm, pipe) == "yes"
                if correctness: total_correct += 1
                print("\nDoctor dialogue:", doctor_dialogue)
                print("\nCorrect answer:", scenario.diagnosis_information())
                print("Scene {}, The diagnosis was ".format(_scenario_id), "CORRECT" if correctness else "INCORRECT", int((total_correct/total_presents)*100))
                break
            # Obtain medical exam from measurement reader
            if "REQUEST TEST" in doctor_dialogue:
                pi_dialogue = meas_agent.inference_measurement(doctor_dialogue,)
                print("Measurement [{}%]:".format(int(((_inf_id+1)/total_inferences)*100)), pi_dialogue)
                patient_agent.add_hist(pi_dialogue)
            # Obtain response from patient
            else:
                if inf_type == "human_patient":
                    pi_dialogue = input("\nResponse to doctor: ")
                else:
                    pi_dialogue = patient_agent.inference_patient(doctor_dialogue)
                print("Patient [{}%]:".format(int(((_inf_id+1)/total_inferences)*100)), pi_dialogue)
                meas_agent.add_hist(pi_dialogue)
            # Prevent API timeouts
            time.sleep(1.0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Medical Diagnosis Simulation CLI')
    parser.add_argument('--openai_api_key', type=str, required=False, help='OpenAI API Key')
    parser.add_argument('--replicate_api_key', type=str, required=False, help='Replicate API Key')
    parser.add_argument('--inf_type', type=str, choices=['llm', 'human_doctor', 'human_patient'], default='llm')
    parser.add_argument('--doctor_bias', type=str, help='Doctor bias type', default='None', choices=["recency", "frequency", "false_consensus", "confirmation", "status_quo", "gender", "race", "sexual_orientation", "cultural", "education", "religion", "socioeconomic"])
    parser.add_argument('--patient_bias', type=str, help='Patient bias type', default='None', choices=["recency", "frequency", "false_consensus", "self_diagnosis", "gender", "race", "sexual_orientation", "cultural", "education", "religion", "socioeconomic"])
    parser.add_argument('--doctor_llm', type=str, default='gpt4')
    parser.add_argument('--patient_llm', type=str, default='gpt4')
    parser.add_argument('--measurement_llm', type=str, default='gpt4')
    parser.add_argument('--moderator_llm', type=str, default='gpt4')
    parser.add_argument('--agent_dataset', type=str, default='MedQA') # MedQA, MIMICIV or NEJM
    parser.add_argument('--doctor_image_request', type=bool, default=False) # whether images must be requested or are provided
    parser.add_argument('--num_scenarios', type=int, default=15, required=False, help='Number of scenarios to simulate')
    parser.add_argument('--total_inferences', type=int, default=20, required=False, help='Number of inferences between patient and doctor')
    parser.add_argument('--anthropic_api_key', type=str, default=None, required=False, help='Anthropic API key for Claude 3.5 Sonnet')
    parser.add_argument('--number_of_sentences', type=str, default="1-2", required=False, help='Number of sentences for doctor to respond with')
    
    args = parser.parse_args()

    main(args.openai_api_key, args.replicate_api_key, args.inf_type, args.doctor_bias, args.patient_bias, args.doctor_llm, args.patient_llm, args.measurement_llm, args.moderator_llm, args.num_scenarios, args.agent_dataset, args.doctor_image_request, args.total_inferences, args.anthropic_api_key, args.number_of_sentences)
