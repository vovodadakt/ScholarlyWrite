import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models.project import Project
from app.routers.auth import get_current_user, get_current_user_optional

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

TEMPLATES_LIST = [
    {
        "name": "IMRaD（理工医）",
        "desc": "Introduction, Methods, Results, and Discussion — 自然科学、工程技术、医学主流格式",
        "category": "empirical",
        "sections": ["引言", "文献综述", "研究方法", "结果与分析", "讨论", "结论"],
    },
    {
        "name": "实证研究（社科）",
        "desc": "问题提出 → 理论假设 → 研究设计 → 数据分析 → 结论讨论",
        "category": "empirical",
        "sections": ["引言", "理论基础与研究假设", "研究设计", "实证分析", "讨论", "结论与展望"],
    },
    {
        "name": "案例研究（管理）",
        "desc": "研究背景 → 文献回顾 → 方法设计 → 案例描述 → 发现与启示",
        "category": "qualitative",
        "sections": ["研究背景与意义", "文献综述", "研究方法与设计", "案例描述", "分析与讨论", "结论与启示"],
    },
    {
        "name": "系统综述与Meta分析",
        "desc": "PRISMA规范的文献筛选、质量评价与效应量合并",
        "category": "review",
        "sections": ["引言", "文献检索策略", "纳入与排除标准", "质量评价", "数据提取与分析", "结果", "讨论", "结论"],
    },
    {
        "name": "范围综述 (Scoping Review)",
        "desc": "Arksey & O'Malley框架，绘制领域研究全景图",
        "category": "review",
        "sections": ["引言", "研究问题", "检索策略", "文献筛选", "数据图表化", "主题分析", "讨论", "结论"],
    },
    {
        "name": "混合方法研究",
        "desc": "量化+质性结合，Creswell设计框架",
        "category": "mixed",
        "sections": ["引言", "哲学立场与研究设计", "量化阶段：方法与结果", "质性阶段：方法与发现", "整合分析", "讨论", "结论"],
    },
    {
        "name": "扎根理论（质化）",
        "desc": "Glaser/Strauss/Charmaz路径，从数据中建构理论",
        "category": "qualitative",
        "sections": ["引言", "方法论立场", "数据收集", "编码过程：开放/主轴/选择", "理论建构", "讨论与反思", "结论"],
    },
    {
        "name": "实验研究（心理/教育）",
        "desc": "假设驱动的随机对照试验或准实验设计",
        "category": "empirical",
        "sections": ["引言与理论背景", "研究假设", "实验设计", "参与者与程序", "数据结果", "讨论", "结论"],
    },
    {
        "name": "纵向研究",
        "desc": "跨时间追踪同类样本，分析变化趋势",
        "category": "empirical",
        "sections": ["引言", "理论基础与假设", "研究设计：波次与样本", "各波次数据分析", "变化轨迹分析", "讨论", "结论"],
    },
    {
        "name": "比较研究",
        "desc": "跨国/跨案例/跨时期比较，寻找差异机制",
        "category": "mixed",
        "sections": ["引言", "比较框架构建", "案例A分析", "案例B分析", "跨案例对比", "理论解释", "结论与启示"],
    },
    {
        "name": "理论建构",
        "desc": "提出新概念或理论模型，论证解释力与边界条件",
        "category": "theoretical",
        "sections": ["引言", "现有理论回顾与局限", "概念界定与维度化", "理论模型构建", "命题提出", "理论贡献", "讨论与结论"],
    },
    {
        "name": "政策分析",
        "desc": "政策效果评估/比较/倡导，面向决策者",
        "category": "theoretical",
        "sections": ["引言：政策背景", "政策框架与分析工具", "政策内容分析", "实施效果评估", "国际比较", "政策建议", "结论"],
    },
    {
        "name": "叙述性综述",
        "desc": "非系统的传统文献综述，适合早期研究阶段",
        "category": "review",
        "sections": ["引言", "领域背景与历史脉络", "主题一：概念与定义", "主题二：主要争论", "主题三：方法学进展", "研究空白", "结论与展望"],
    },
    {
        "name": "行动研究（教育/社区）",
        "desc": "实践者即研究者，计划-行动-反思循环",
        "category": "qualitative",
        "sections": ["引言：实践问题", "文献回顾", "行动方案设计", "第一轮行动与反思", "第二轮行动与反思", "效果评估", "结论与实践启示"],
    },
    {
        "name": "内容分析",
        "desc": "对文本/图像/视频做系统编码与量化统计",
        "category": "empirical",
        "sections": ["引言", "研究问题与假设", "样本选择与数据来源", "编码框架与信度检验", "描述性统计", "推论性分析", "讨论", "结论"],
    },
    {
        "name": "调查研究（问卷法）",
        "desc": "大样本问卷调查，测量态度/行为/特征，量化分析",
        "category": "empirical",
        "sections": ["引言", "文献回顾与研究假设", "问卷设计与预测试", "抽样与数据收集", "信效度检验", "数据分析结果", "讨论", "结论"],
    },
    {
        "name": "民族志/田野调查",
        "desc": "长期浸入式观察，理解群体文化与行为",
        "category": "qualitative",
        "sections": ["引言：田野背景", "进入田野与研究者角色", "数据收集：观察与访谈", "数据编码与主题提炼", "文化解释", "理论对话", "结论与反思"],
    },
    {
        "name": "话语分析",
        "desc": "语言/文本/图像如何建构社会现实",
        "category": "qualitative",
        "sections": ["引言", "理论视角：话语与社会", "数据来源与选择", "分析框架", "话语策略分析", "权力与意识形态", "讨论", "结论"],
    },
    {
        "name": "德尔菲研究",
        "desc": "专家多轮征询达成共识，适合新兴领域",
        "category": "empirical",
        "sections": ["引言", "研究设计与专家遴选", "第一轮：开放性征询", "第二轮：评分与反馈", "第三轮：共识达成", "结果分析与讨论", "结论"],
    },
    {
        "name": "计算社会科学",
        "desc": "大数据/网络分析/机器学习驱动的社科研究",
        "category": "empirical",
        "sections": ["引言", "研究问题与数据来源", "数据预处理与特征工程", "分析方法与模型", "结果呈现", "鲁棒性检验", "讨论", "结论"],
    },
    {
        "name": "设计科学研究 (DSR)",
        "desc": "信息系统/工程领域——构建并评估人造物",
        "category": "theoretical",
        "sections": ["引言", "问题识别与动机", "设计目标与需求", "设计与开发过程", "演示与评估", "理论贡献与设计原则", "结论"],
    },
    {
        "name": "文献计量分析",
        "desc": "引文分析/共词分析/知识图谱，绘制领域全景",
        "category": "review",
        "sections": ["引言", "数据来源与检索策略", "描述性统计", "引文网络分析", "共词与聚类分析", "研究热点与趋势", "局限与展望", "结论"],
    },
    {
        "name": "随机对照试验 (RCT)",
        "desc": "医学/公共卫生/教育领域的金标准设计",
        "category": "empirical",
        "sections": ["引言", "研究设计与随机化方案", "参与者与伦理审批", "干预措施", "结局指标与测量", "统计分析", "讨论", "结论"],
    },
    {
        "name": "质性元综合",
        "desc": "整合多项质性研究成果，生成新解释",
        "category": "review",
        "sections": ["引言", "文献检索与筛选", "质量评价", "提取与编码", "主题综合", "理论建构", "讨论与反思", "结论"],
    },
    {
        "name": "干预研究",
        "desc": "设计/实施/评估特定干预方案的效果",
        "category": "empirical",
        "sections": ["引言与问题背景", "干预方案设计", "实施过程与保真度", "评估方法与数据收集", "干预效果分析", "过程评估", "讨论", "结论"],
    },
    {
        "name": "跨界/跨学科研究",
        "desc": "多个学科视角融合解决复杂问题",
        "category": "mixed",
        "sections": ["引言：问题复杂性", "学科立场与方法", "知识整合框架", "交叉分析", "新兴洞见", "方法论反思", "结论"],
    },
]

# Research note field definitions per template category
NOTE_FIELDS = {
    "empirical": [
        {"key": "topic", "label": "论文方向", "type": "input", "placeholder": "AI 将从对话中提取..."},
        {"key": "keywords", "label": "核心概念 / 关键词", "type": "input", "placeholder": "如：社会比较, 自尊, 青少年"},
        {"key": "hypothesis", "label": "研究假设", "type": "textarea", "placeholder": "如：H1: 社交媒体使用时长与自尊水平负相关\nH2: ..."},
        {"key": "variables", "label": "变量定义", "type": "textarea", "placeholder": "自变量: ...\n因变量: ...\n控制变量: ...\n调节/中介变量: ..."},
        {"key": "methodology", "label": "研究方法", "type": "textarea", "placeholder": "实验/问卷/二手数据...\n统计方法: t检验/ANOVA/回归/SEM..."},
        {"key": "sample", "label": "样本与数据", "type": "textarea", "placeholder": "目标人群、样本量、抽样方法、数据来源..."},
        {"key": "instruments", "label": "测量工具", "type": "textarea", "placeholder": "量表名称、信度(Cronbach's α)、效度、题项数..."},
        {"key": "experiment", "label": "实验设计与流程", "type": "textarea", "placeholder": "实验条件分组、刺激材料、操作流程、操纵检验..."},
        {"key": "theory", "label": "理论框架", "type": "input", "placeholder": "如：社会比较理论 (Festinger, 1954)"},
        {"key": "contributions", "label": "预期贡献", "type": "textarea", "placeholder": "理论贡献、实践意义、方法创新..."},
    ],
    "review": [
        {"key": "topic", "label": "综述主题", "type": "input", "placeholder": "AI 将从对话中提取..."},
        {"key": "keywords", "label": "核心概念 / 关键词", "type": "input", "placeholder": "检索关键词组合..."},
        {"key": "research_questions", "label": "研究问题", "type": "textarea", "placeholder": "本综述要回答哪些问题？\n如：RQ1: ... RQ2: ..."},
        {"key": "search_strategy", "label": "检索策略", "type": "textarea", "placeholder": "数据库: Web of Science/PubMed/Scopus...\n检索式: ...\n时间范围: ..."},
        {"key": "inclusion_criteria", "label": "纳入与排除标准", "type": "textarea", "placeholder": "纳入: ...\n排除: ...\n筛选流程: PRISMA流程图"},
        {"key": "quality_assessment", "label": "质量评价方法", "type": "textarea", "placeholder": "Cochrane RoB/AMSTAR-2/QUADAS-2..."},
        {"key": "analysis_method", "label": "数据提取与分析方法", "type": "textarea", "placeholder": "提取字段: ...\n效应量合并: ...\n异质性检验: ...\n亚组分析: ..."},
        {"key": "theory", "label": "理论视角", "type": "input", "placeholder": "用于解释综述发现的理论框架"},
        {"key": "contributions", "label": "预期贡献", "type": "textarea", "placeholder": "对领域的系统性理解、研究空白识别..."},
    ],
    "qualitative": [
        {"key": "topic", "label": "研究主题", "type": "input", "placeholder": "AI 将从对话中提取..."},
        {"key": "keywords", "label": "核心概念 / 关键词", "type": "input", "placeholder": "如：教师身份认同, 叙事探究"},
        {"key": "research_questions", "label": "研究问题", "type": "textarea", "placeholder": "探索性问题，如：XX 如何理解/体验/建构..."},
        {"key": "methodology", "label": "方法论立场", "type": "textarea", "placeholder": "现象学/扎根理论/民族志/叙事探究/案例研究..."},
        {"key": "data_collection", "label": "数据收集", "type": "textarea", "placeholder": "深度访谈/参与观察/焦点小组/文档分析...\n参与者: ...\n抽样策略: 目的性/理论/滚雪球..."},
        {"key": "coding_approach", "label": "编码与分析策略", "type": "textarea", "placeholder": "开放编码→主轴编码→选择编码\n或: 主题分析(Braun & Clarke)六步骤\n软件: NVivo/ATLAS.ti/手工"},
        {"key": "theory", "label": "理论视角", "type": "input", "placeholder": "如：社会建构主义、符号互动论"},
        {"key": "contributions", "label": "预期贡献", "type": "textarea", "placeholder": "对现象的新理解、理论发展、实践启示..."},
    ],
    "mixed": [
        {"key": "topic", "label": "研究主题", "type": "input", "placeholder": "AI 将从对话中提取..."},
        {"key": "keywords", "label": "核心概念 / 关键词", "type": "input", "placeholder": "如：组织韧性, 数字化转型"},
        {"key": "research_questions", "label": "研究问题", "type": "textarea", "placeholder": "量化问题: ...\n质性问题: ...\n整合问题: ..."},
        {"key": "quant_method", "label": "量化阶段设计", "type": "textarea", "placeholder": "研究设计、样本、测量工具、统计方法..."},
        {"key": "qual_method", "label": "质性阶段设计", "type": "textarea", "placeholder": "方法论、数据收集、编码策略..."},
        {"key": "integration", "label": "整合策略", "type": "textarea", "placeholder": "聚敛设计/解释性序列/探索性序列...\n整合点: 数据收集/分析/解释阶段"},
        {"key": "theory", "label": "理论框架", "type": "input", "placeholder": "指导混合方法设计的理论视角"},
        {"key": "contributions", "label": "预期贡献", "type": "textarea", "placeholder": "方法论贡献、多维度的研究发现..."},
    ],
    "theoretical": [
        {"key": "topic", "label": "研究主题", "type": "input", "placeholder": "AI 将从对话中提取..."},
        {"key": "keywords", "label": "核心概念 / 关键词", "type": "input", "placeholder": "如：动态能力, 组织惯例"},
        {"key": "theory_gap", "label": "现有理论缺口", "type": "textarea", "placeholder": "现有理论在哪些方面不足？\n矛盾、空白、边界不清..."},
        {"key": "concepts", "label": "核心概念界定", "type": "textarea", "placeholder": "概念A: 定义、维度、测量方式...\n概念B: ..."},
        {"key": "propositions", "label": "理论命题", "type": "textarea", "placeholder": "命题1: ...\n命题2: ...\n命题间的逻辑关系: ..."},
        {"key": "scope", "label": "边界条件", "type": "textarea", "placeholder": "理论适用的情境、层次(个体/团队/组织)、限界..."},
        {"key": "contributions", "label": "理论贡献", "type": "textarea", "placeholder": "对已有理论的拓展/修正/整合，新解释机制..."},
    ],
    "general": [
        {"key": "topic", "label": "论文方向", "type": "input", "placeholder": "AI 将从对话中提取..."},
        {"key": "keywords", "label": "核心概念 / 关键词", "type": "input", "placeholder": "如：社会比较, 自尊, 青少年"},
        {"key": "methodology", "label": "研究方法论", "type": "textarea", "placeholder": "如：问卷调查 + 结构方程模型"},
        {"key": "experiment", "label": "实验设计", "type": "textarea", "placeholder": "样本、变量、测量工具、实验流程..."},
        {"key": "theory", "label": "理论框架", "type": "input", "placeholder": "如：社会比较理论 (Festinger, 1954)"},
        {"key": "contributions", "label": "预期贡献", "type": "textarea", "placeholder": "理论贡献、实践意义、创新点..."},
    ],
}

JOURNAL_TEMPLATES = [
    {"name": "Nature", "desc": "结构紧凑，强调新闻价值", "style": "nature"},
    {"name": "Science", "desc": "短报告+补充材料", "style": "science"},
    {"name": "IEEE", "desc": "双栏，工程/计算机", "style": "ieee"},
    {"name": "APA 7th", "desc": "心理学/教育学/社科", "style": "apa"},
    {"name": "GB/T 7714", "desc": "中文核心期刊国标", "style": "gbt"},
    {"name": "MLA 9th", "desc": "人文学科/语言文学", "style": "mla"},
    {"name": "Chicago", "desc": "历史/人文/社科综合", "style": "chicago"},
    {"name": "Vancouver", "desc": "生物医学/编号制引用", "style": "vancouver"},
    {"name": "Harvard", "desc": "作者-年份制，商科常用", "style": "harvard"},
    {"name": "通用学术", "desc": "不指定格式，自由导出", "style": "general"},
]


@router.get("/")
async def root(request: Request):
    user = await get_current_user_optional(request)
    if user:
        return RedirectResponse("/projects")
    return templates.TemplateResponse("landing.html", {"request": request, "current_user": None})


@router.get("/about")
async def about_page(request: Request):
    user = await get_current_user_optional(request)
    return templates.TemplateResponse("about.html", {"request": request, "current_user": user})


@router.get("/projects")
async def project_list(request: Request):
    user = await get_current_user_optional(request)
    if not user:
        return RedirectResponse("/auth/login")

    async with async_session() as db:
        result = await db.execute(
            select(Project)
            .where(Project.user_id == user.id)
            .order_by(Project.updated_at.desc())
        )
        projects = result.scalars().all()

        proj_list = []
        for p in projects:
            proj_list.append({
                "id": p.id,
                "title": p.title,
                "description": p.description,
                "status": p.status,
                "word_count": p.word_count,
                "deadline": p.deadline,
                "tags": p.tags or [],
                "template_name": p.template_name,
                "journal_style": p.journal_style,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            })

    return templates.TemplateResponse(
        "projects/list.html",
        {"request": request, "current_user": user, "projects": proj_list},
    )


@router.get("/templates")
async def templates_page(request: Request):
    user = await get_current_user_optional(request)
    if not user:
        return RedirectResponse("/auth/login")
    return templates.TemplateResponse(
        "projects/templates.html",
        {
            "request": request,
            "current_user": user,
            "templates_list": TEMPLATES_LIST,
            "journal_templates": JOURNAL_TEMPLATES,
        },
    )


@router.get("/projects/create")
async def create_project_page(request: Request):
    return RedirectResponse("/templates")


@router.post("/api/projects")
async def create_project(request: Request, user=Depends(get_current_user)):
    data = await request.json()
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()

    if not title:
        raise HTTPException(status_code=400, detail="Title is required")

    async with async_session() as db:
        project = Project(
            user_id=user.id,
            title=title,
            description=description,
            tags=data.get("tags", []),
            deadline=data.get("deadline"),
            template_name=data.get("template_name", ""),
            journal_style=data.get("journal_style", ""),
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)

        return {
            "id": str(project.id),
            "title": project.title,
            "description": project.description,
            "status": project.status,
            "tags": project.tags,
            "deadline": project.deadline,
        }


@router.get("/projects/{project_id}")
async def project_detail(project_id: str, request: Request):
    user = await get_current_user_optional(request)
    if not user:
        return RedirectResponse("/auth/login")

    async with async_session() as db:
        project = await db.get(
            Project,
            project_id,
            options=[selectinload(Project.outlines), selectinload(Project.chapters)],
        )
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        all_chapters = sorted(project.chapters, key=lambda c: (c.chapter_order, c.chapter_number))
        top_level = [c for c in all_chapters if c.parent_id is None]

        def build_tree(chapters):
            result = []
            for c in chapters:
                children = [ch for ch in all_chapters if ch.parent_id == c.id]
                result.append({
                    "id": str(c.id),
                    "title": c.title,
                    "content": c.content,
                    "chapter_order": c.chapter_order,
                    "chapter_number": c.chapter_number or "",
                    "level": c.level,
                    "status": c.status,
                    "children": build_tree(children) if children else [],
                })
            return result

        chapters_data = build_tree(top_level)

        need_ideation = (
            project.status == "ideation"
            or (not project.outlines and not chapters_data)
        )

        proj_meta = {
            "word_count": project.word_count,
            "deadline": project.deadline,
            "tags": project.tags or [],
            "template_name": project.template_name,
            "journal_style": project.journal_style,
        }

        return templates.TemplateResponse(
            "projects/detail.html",
            {
                "request": request,
                "current_user": user,
                "project": project,
                "outline": project.outlines[0] if project.outlines else None,
                "chapters": chapters_data,
                "need_ideation": need_ideation,
                "proj_meta": proj_meta,
            },
        )


@router.get("/projects/{project_id}/outline")
async def outline_page(project_id: str, request: Request):
    """Independent outline editing page."""
    user = await get_current_user_optional(request)
    if not user:
        return RedirectResponse("/auth/login")

    async with async_session() as db:
        project = await db.get(
            Project,
            project_id,
            options=[selectinload(Project.outlines), selectinload(Project.chapters)],
        )
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        outline = project.outlines[0] if project.outlines else None

    return templates.TemplateResponse(
        "projects/outline.html",
        {
            "request": request,
            "current_user": user,
            "project": project,
            "outline": outline,
        },
    )


@router.get("/projects/{project_id}/references")
async def references_page(project_id: str, request: Request):
    """Dedicated reference management page."""
    user = await get_current_user_optional(request)
    if not user:
        return RedirectResponse("/auth/login")

    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

    return templates.TemplateResponse(
        "projects/references.html",
        {
            "request": request,
            "current_user": user,
            "project": project,
        },
    )


@router.get("/projects/{project_id}/submission-checklist")
async def submission_checklist_page(project_id: str, request: Request):
    """Submission checklist page."""
    user = await get_current_user_optional(request)
    if not user:
        return RedirectResponse("/auth/login")

    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

    return templates.TemplateResponse(
        "projects/submission_checklist.html",
        {
            "request": request,
            "current_user": user,
            "project": project,
        },
    )


@router.delete("/api/projects/{project_id}")
async def delete_project(project_id: str, user=Depends(get_current_user)):
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        await db.delete(project)
        await db.commit()

    return {"ok": True}


@router.put("/api/projects/{project_id}")
async def update_project(project_id: str, request: Request, user=Depends(get_current_user)):
    """Update project metadata: tags, deadline, word_count, title, description."""
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404)

        data = await request.json()
        for field in ("title", "description", "deadline", "template_name", "journal_style"):
            if field in data:
                setattr(project, field, data[field])
        if "tags" in data:
            project.tags = data["tags"]
        if "word_count" in data:
            project.word_count = data["word_count"]
        await db.commit()
    return {"ok": True}
