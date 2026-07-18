# AI/ML skill routing

For empirical AI/ML research, use `applied-ml-research` as the default methodology and select the
smallest set of installed specialist skills that matches the work. State which research skill is
being used and why. Do not substitute frontend `audit` or another unrelated skill. Code-quality
review uses `thermo-nuclear-code-quality-review`; it is not a replacement for research methodology.
Apply the same routing to subagents: delegation prompts must name the selected AI/ML skill and must
not request a generic or frontend audit skill.

When the user asks for AI/ML research skills, route from this installed catalog:

- Orchestration: Autoresearch.
- Model architecture: LitGPT, Mamba, RWKV, NanoGPT, TorchTitan.
- Tokenization: HuggingFace Tokenizers, SentencePiece.
- Fine-tuning: Axolotl, LLaMA-Factory, Unsloth, PEFT.
- Mechanistic interpretability: TransformerLens, SAELens, pyvene, nnsight.
- Data processing: Ray Data, NeMo Curator.
- Post-training: TRL Fine-Tuning, GRPO-RL-Training (TRL), OpenRLHF, SimPO, verl, slime, miles,
  torchforge.
- Safety and alignment: Constitutional AI, LlamaGuard, NeMo Guardrails, Prompt Guard.
- Distributed training: Megatron-Core, DeepSpeed, PyTorch FSDP2, Accelerate, PyTorch Lightning,
  Ray Train.
- Optimization: Flash Attention, bitsandbytes, GPTQ, AWQ, HQQ, GGUF.
- Evaluation: lm-evaluation-harness, BigCode Evaluation Harness, NeMo Evaluator.
- Infrastructure: Modal, SkyPilot, Lambda Labs.
- Inference and serving: vLLM, TensorRT-LLM, llama.cpp, SGLang.
- Agents: LangChain, LlamaIndex, CrewAI, AutoGPT.
- RAG: Chroma, FAISS, Sentence Transformers, Pinecone, Qdrant.
- Multimodal: CLIP, Whisper, LLaVA, Stable Diffusion, Segment Anything, BLIP-2, AudioCraft.
- Prompt engineering: DSPy, Instructor, Guidance, Outlines.
- MLOps: Weights & Biases, MLflow, TensorBoard.
- Observability: LangSmith, Phoenix.
- Emerging techniques: MoE Training, Model Merging, Long Context, Speculative Decoding,
  Knowledge Distillation, Model Pruning.
- ML paper writing: ML Paper Writing, Academic Plotting.
- Ideation: Research Brainstorming, Creative Thinking.
- Agent-native research artifacts: ARA Compiler, ARA Research Manager, ARA Rigor Reviewer.

Use only skills relevant to the concrete task; do not load the full catalog at once. For evaluation
or label adjudication, inspect raw outputs and failure slices before trusting aggregate metrics.
