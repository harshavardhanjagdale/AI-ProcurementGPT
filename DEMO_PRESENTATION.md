ProcureGPT Demo

1.  to demonstrate ProcureGPT, an AI-powered procurement platform built
    using an Agentic AI architecture. The goal is to automate the
    complete procurement lifecycle—from understanding a natural language
    request to supplier selection, quotation comparison, human approval,
    and purchase order generation—while keeping a human in control.”

2.  Business Problem (45 seconds) “Traditional procurement involves
    multiple manual steps: understanding requirements, finding
    suppliers, emailing RFQs, waiting for responses, comparing
    quotations, negotiating, and finally creating purchase orders.
    ProcureGPT automates these repetitive tasks while ensuring
    transparency, auditability, and human approval.”

3.  12 Nodes
1) parse_request - it validates the natural language to str(qty,item,budget,direct supplier) and validates >1 item , qty

2) create_rfq_record - it insert the rfq into rfq table and rfq items and assign a latest rfq no `RFQ-YYYY-NNNNN` | RFQ Agent

3) resolve_direct_supplier - it check the direct supplier from natural language and validates

4) select_vendors - Embeds the RFQ text , cosine similarity ranking , vector embedding | vendor agent

5) generate_rfq_emails - LLM drafts an RFQ email per selected supplier including there name and RFQ ID | Email Agent |

6) send_rfq_emails - Sends the RFQ emails via SMTP to the supplier | Email Agent |

7) await_supplier_replies - raph pauses here until a reply arrives | Inbox Agent | Human Interreption

8) ocr_extract - complex 3 step agents workflow (download-> convert pdf to image(pdf2image package) -> image to text (tessrack)scattered text)send to llm->        llm parse data and get the corrected text input details

9) user_decision_gate - graph pauses for approve/negotiate/cancel | Human |

10) negotiate_with_suppliers - LLM drafts + sends a counter-offer email, records a `negotiations` row | Negotiation Agent |

11) generate_purchase_order - create a PO rows (ReportLab package) Po agent| send po in email drafting and mentioning same rfq id and same qty and item

12) send_po_email - Emails the PO (with the PDF attached) to the supplier | Email Agent |

## Vendor Selection-
-embeddings are precomputed and stored as a `BLOB` and used cosine similarity

## OCR Pipeline - 
1) PDf to image - pdf2image at 300dpi used poppler package and convert to png format
2) Image to raw text - tesseract used oem3 engine
3) Raw Text to structure JSOn - messy OCR text becomes clean fields
## (Pre and Post Hooks added) - before extraction check email id and post- check the item and actual supplier name
.claude files ,skill files
## Email in/out-
Outbound - Used SMPT 	
Inbound - IMAP- via aiosmtplib and matches `RFQ-YYYY-NNNNN` token in the subject 


## Claude Best Practices - 
 	1) PreLLM Hooks and PostLLM Hooks
	2) Propmt Evaluation
	3) Prompt Catching - emperial content type,cost saving(if more than 2800 token) stays for 5 mins -90% cost saving
## langsmith orchestration
validation of no item and wrong quotation send - prepost ocr validation in wrong supplier

LLM layer — multi-provider, one interface
- openAI , Anthropic , Gemini
