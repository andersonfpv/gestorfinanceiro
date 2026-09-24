import { useCallback, useEffect, useMemo, useState } from "react";
import { BrowserRouter, useNavigate } from "react-router-dom";
import axios from "axios";
import { BarChart3, BookOpen, ChevronDown, CircleDollarSign, Download, Filter, LayoutDashboard, LogOut, Menu, Plus, Settings2, Tags, Trash2, Users, WalletCards, X } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import "@/App.css";

const API=`${(process.env.REACT_APP_BACKEND_URL||"").replace(/\/+$/,"")}/api`; const amountToCents=value=>{const match=/^(-?)(\d+)(?:[.,](\d{1,2}))?$/.exec(String(value??"0").trim());if(!match)return 0;return(match[1]? -1:1)*(Number(match[2])*100+Number((match[3]||"").padEnd(2,"0")))}; const moneyCents=cents=>new Intl.NumberFormat("pt-BR",{style:"currency",currency:"BRL"}).format(cents/100); const money=value=>moneyCents(amountToCents(value)); const toIsoDate=value=>{const raw=String(value??"").trim();if(/^\d{4}-\d{2}-\d{2}$/.test(raw))return raw;const match=/^(\d{2})\/(\d{2})\/(\d{4})$/.exec(raw);return match?`${match[3]}-${match[2]}-${match[1]}`:""}; const displayDate=value=>{const iso=toIsoDate(value);if(!iso)return String(value||"");const [year,month,day]=iso.split("-");return `${day}/${month}/${year}`}; const api=(url,opts={})=>axios({url:`${API}${url}`,withCredentials:true,...opts}).then(r=>r.data); const today=()=>{const date=new Date();return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`}; const monthBounds=()=>{const [year,month]=today().split("-").map(Number);const next=new Date(year,month,1);const pad=value=>String(value).padStart(2,"0");return{date_from:`${year}-${pad(month)}-01`,date_to:`${next.getFullYear()}-${pad(next.getMonth()+1)}-01`}};
function Login({onLogin,authConfig}){const [error,setError]=useState(new URLSearchParams(window.location.search).has("auth_error")?"Não foi possível concluir o acesso com Google. Tente novamente.":""); const start=()=>{window.location.assign(`${API}/auth/google/start`)}; return <main className="auth-page"><div className="auth-art"><div className="brand"><CircleDollarSign/> Meu Controle Financeiro</div><div><span className="eyebrow">Seu dinheiro, mais claro</span><h1>Decisões tranquilas começam com uma visão simples.</h1><p>Organize sua vida financeira, convide quem importa e acompanhe tudo em um só lugar.</p></div></div><section className="auth-box"><div className="brand mobile-brand"><CircleDollarSign/> Meu Controle Financeiro</div><span className="eyebrow">Acesso seguro</span><h2>Bem-vindo de volta</h2><p className="muted">Entre para continuar seu controle financeiro.</p>{authConfig.google_enabled&&<button data-testid="login-google-button" className="primary wide" onClick={start}>Continuar com Google</button>}{authConfig.google_enabled&&authConfig.demo_enabled&&<div className="divider">ou</div>}{authConfig.demo_enabled&&<button data-testid="login-demo-button" className="secondary wide" onClick={()=>api("/auth/demo",{method:"POST"}).then(onLogin).catch(()=>setError("Não foi possível iniciar a demonstração."))}>Entrar na demonstração</button>}{!authConfig.google_enabled&&!authConfig.demo_enabled&&<div className="error">Nenhum método de acesso está configurado. Configure o login Google ou habilite a demonstração.</div>}{error&&<div data-testid="login-error" className="error">{error}</div>}<small>Ao continuar, você concorda com nossos termos de uso.</small></section></main>}
function Shell({user,onLogout,children,control,setControl,controls,onAccount}){const nav=useNavigate(),[menuOpen,setMenuOpen]=useState(false); return <div className="app-shell"><aside className={menuOpen?"mobile-open":""}><div className="brand"><CircleDollarSign/> Meu Controle</div><div className="control-picker"><span>CONTROLE ATIVO</span><button data-testid="active-control-selector" onClick={()=>controls.length>1&&setControl(controls[(controls.indexOf(control)+1)%controls.length])}>{control?.name||"Selecione um controle"}<ChevronDown size={16}/></button></div><nav><button data-testid="nav-dashboard" className={location.pathname==="/"?"active":""} onClick={()=>nav("/")}><LayoutDashboard/> Visão geral</button><button data-testid="nav-transactions" onClick={()=>nav("/lancamentos")}><BookOpen/> Lançamentos</button><button data-testid="nav-tags" onClick={()=>nav("/tags")}><Tags/> Tags</button><button data-testid="nav-members" onClick={()=>nav("/membros")}><Users/> Pessoas</button></nav><button data-testid="logout-button" className="logout" onClick={onLogout}><LogOut/> Sair</button></aside><main className="content"><header><button className="menu-btn" data-testid="mobile-menu-button" onClick={()=>setMenuOpen(!menuOpen)} aria-expanded={menuOpen}><Menu/></button><div><span className="eyebrow">{new Date().toLocaleDateString("pt-BR",{weekday:"long",day:"numeric",month:"long"})}</span><h1>{control?.name||"Meu controle"}</h1></div><button className="profile profile-button" data-testid="account-settings-button" aria-label="Configurações da conta" onClick={onAccount}><div className="avatar">{user.name?.[0]}</div><span>{user.name}</span><Settings2 size={17}/></button></header>{children}</main><div className="bottom-nav"><button data-testid="mobile-nav-dashboard" onClick={()=>nav("/")}><LayoutDashboard/>Início</button><button data-testid="mobile-nav-transactions" onClick={()=>nav("/lancamentos")}><BookOpen/>Lançamentos</button><button data-testid="mobile-nav-tags" onClick={()=>nav("/tags")}><Tags/>Tags</button><button data-testid="mobile-nav-members" onClick={()=>nav("/membros")}><Users/>Pessoas</button></div></div>}
function Modal({title,onClose,children}){return <div className="modal-backdrop"><div className="modal"><button data-testid="modal-close-button" className="icon-btn close" onClick={onClose}><X/></button><h2>{title}</h2>{children}</div></div>}
function Filters({filters,setFilters,tags,members}){return <div className="filters"><div className="filter-title"><Filter size={16}/> Filtros</div><select data-testid="filter-period" value={filters.period} onChange={e=>setFilters({...filters,period:e.target.value})}><option value="all">Todo o período</option><option value="month">Este mês</option></select><select data-testid="filter-type" value={filters.type} onChange={e=>setFilters({...filters,type:e.target.value})}><option value="all">Todos os tipos</option><option value="income">Entradas</option><option value="expense">Saídas</option></select><select data-testid="filter-tag" value={filters.tag} onChange={e=>setFilters({...filters,tag:e.target.value})}><option value="all">Todas as tags</option>{tags.map(t=><option key={t.tag_id} value={t.tag_id}>{t.name}</option>)}</select><select data-testid="filter-member" value={filters.user} onChange={e=>setFilters({...filters,user:e.target.value})}><option value="all">Todas as pessoas</option>{members.map(m=><option key={m.user_id} value={m.user_id}>{m.email}</option>)}</select></div>}
function Dashboard({control,tags,members,transactions,onRefresh,canEdit,isOwner}) {
  const [filters,setFilters]=useState({period:"all",type:"all",tag:"all",user:"all"});
  const [show,setShow]=useState(false);
  const [summary,setSummary]=useState({entries_total:"0.00",expenses_total:"0.00",transaction_count:0,expenses_by_tag:[],trend:[]});
  const [summaryError,setSummaryError]=useState("");
  useEffect(()=>{
    const params=new URLSearchParams();
    if(filters.period==="month"){
      const bounds=monthBounds();
      params.set("date_from",bounds.date_from);
      params.set("date_to",bounds.date_to);
    }
    if(filters.type!=="all")params.set("type",filters.type);
    if(filters.tag!=="all")params.set("tag_id",filters.tag);
    if(filters.user!=="all")params.set("user_id",filters.user);
    api("/controls/"+control.control_id+"/summary?"+params.toString())
      .then(data=>{setSummary(data);setSummaryError("")})
      .catch(()=>setSummaryError("Não foi possível atualizar o resumo financeiro."));
  },[control.control_id,filters.period,filters.type,filters.tag,filters.user]);
  const recent=useMemo(()=>transactions.filter(t=>
    (filters.period==="all"||toIsoDate(t.date).slice(0,7)===today().slice(0,7))&&
    (filters.type==="all"||t.type===filters.type)&&
    (filters.tag==="all"||t.tag_id===filters.tag)&&
    (filters.user==="all"||t.user_id===filters.user)
  ).slice(0,5),[transactions,filters]);
  const incomeCents=amountToCents(summary.entries_total);
  const expenseCents=amountToCents(summary.expenses_total);
  const byTag=summary.expenses_by_tag.map(item=>({name:item.name,value:Number(item.amount),color:item.color}));
  const trend=summary.trend.map(item=>({date:item.date,Entradas:Number(item.entries_total),Saídas:Number(item.expenses_total)}));
  const addDemo=()=>api("/controls/"+control.control_id+"/demo-data",{method:"POST"}).then(onRefresh);
  const removeDemo=()=>api("/controls/"+control.control_id+"/demo-data",{method:"DELETE"}).then(onRefresh);
  return <>
    <div className="toolbar"><div><span className="eyebrow">Resumo filtrado</span><p data-testid="dashboard-description" className="muted">Acompanhe o que entrou e saiu do seu controle.</p></div><div className="toolbar-actions">{isOwner&&<><button data-testid="add-demo-button" className="secondary" onClick={addDemo}><Download size={16}/> Adicionar demonstração</button><button data-testid="remove-demo-button" className="secondary" onClick={removeDemo}><Trash2 size={16}/> Remover demonstração</button></>}{canEdit&&<button data-testid="new-transaction-button" className="primary" onClick={()=>setShow(true)}><Plus size={17}/> Novo lançamento</button>}</div></div>
    <Filters filters={filters} setFilters={setFilters} tags={tags} members={members}/>
    {summaryError&&<div className="error">{summaryError}</div>}
    <section className="stats">
      <div className="stat balance"><span>Resultado líquido</span><strong data-testid="balance-value">{moneyCents(incomeCents-expenseCents)}</strong><small>Entradas menos saídas nos filtros</small></div>
      <div className="stat"><span>Entradas</span><strong data-testid="income-total" className="positive">{moneyCents(incomeCents)}</strong><small>No período selecionado</small></div>
      <div className="stat"><span>Saídas</span><strong data-testid="expense-total" className="negative">{moneyCents(expenseCents)}</strong><small>No período selecionado</small></div>
      <div className="stat"><span>Lançamentos</span><strong data-testid="transaction-count">{summary.transaction_count}</strong><small>Registros encontrados</small></div>
    </section>
    <section className="charts">
      <div className="panel chart-large"><div className="panel-head"><div><h3>Fluxo ao longo do tempo</h3><span className="muted">Comparativo diário</span></div><BarChart3 size={19}/></div><ResponsiveContainer width="100%" height={230}><BarChart data={trend}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0"/><XAxis dataKey="date" tickFormatter={displayDate}/><YAxis/><Tooltip formatter={money}/><Legend/><Bar dataKey="Entradas" fill="#10b981" radius={[4,4,0,0]}/><Bar dataKey="Saídas" fill="#f97316" radius={[4,4,0,0]}/></BarChart></ResponsiveContainer></div>
      <div className="panel"><div className="panel-head"><div><h3>Onde você gasta</h3><span className="muted">Por tag</span></div><Tags size={19}/></div>{byTag.length?<ResponsiveContainer width="100%" height={230}><PieChart><Pie data={byTag} dataKey="value" nameKey="name" innerRadius={55} outerRadius={82} paddingAngle={3}>{byTag.map(item=><Cell key={item.name} fill={item.color}/>)}</Pie><Tooltip formatter={money}/><Legend/></PieChart></ResponsiveContainer>:<div data-testid="empty-chart" className="empty">Adicione lançamentos para visualizar</div>}</div>
    </section>
    <section className="panel recent"><div className="panel-head"><div><h3>Últimos lançamentos</h3><span className="muted">Atualizados agora</span></div><button data-testid="view-all-transactions" className="link-btn" onClick={()=>location.href="/lancamentos"}>Ver todos</button></div>{recent.map(t=><div className="transaction-row" key={t.transaction_id}><div className={"tx-icon "+t.type}><CircleDollarSign size={17}/></div><div className="tx-info"><strong>{t.description}</strong><span>{displayDate(t.date)} · {tags.find(x=>x.tag_id===t.tag_id)?.name||"Sem tag"}</span></div><b className={t.type}>{t.type==="income"?"+":"−"}{money(t.amount)}</b></div>)}{!recent.length&&<div data-testid="empty-transactions" className="empty">Ainda não há lançamentos neste controle.</div>}</section>
    {show&&canEdit&&<TransactionModal control={control} tags={tags} onClose={()=>setShow(false)} onSaved={()=>{setShow(false);onRefresh()}}/>}
  </>;
}
function TransactionsPage({control,tags,transactions,onRefresh,user,members}) {
  const [query,setQuery]=useState("");
  const [sort,setSort]=useState("date");
  const [page,setPage]=useState(1);
  const [result,setResult]=useState({items:[],total:0,page:1,page_size:25});
  const [editing,setEditing]=useState(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  const role=members.find(member=>member.user_id===user.user_id)?.role;
  const canEdit=role==="owner"||role==="editor";
  const isOwner=role==="owner";
  const load=useCallback(()=>{
    const params=new URLSearchParams({page:String(page),page_size:"25",sort,q:query});
    return api("/controls/"+control.control_id+"/transactions?"+params.toString())
      .then(data=>{setResult(data);setError("")})
      .catch(()=>setError("Não foi possível carregar os lançamentos."));
  },[control.control_id,page,query,sort]);
  useEffect(()=>{
    setLoading(true);
    load().finally(()=>setLoading(false));
  },[load]);
  const rows=result.items;
  const pageCount=Math.max(1,Math.ceil(result.total/25));
  const remove=async transaction=>{
    if(!window.confirm("Excluir “"+transaction.description+"”?"))return;
    try{
      await api("/controls/"+control.control_id+"/transactions/"+transaction.transaction_id,{method:"DELETE"});
      if(rows.length===1&&page>1)setPage(page-1);else await load();
      onRefresh();
    }catch(e){setError(e.response?.data?.detail||"Não foi possível excluir o lançamento.")}
  };
  return <section className="panel page-panel transactions-page">
    <div className="panel-head"><div><span className="eyebrow">Movimentações</span><h2>Todos os lançamentos</h2><p className="muted">Consulte e organize cada entrada e saída.</p></div><BookOpen/></div>
    <div className="list-tools">
      <input data-testid="transactions-search-input" placeholder="Buscar por descrição" value={query} onChange={e=>{setPage(1);setQuery(e.target.value)}}/>
      <select data-testid="transactions-sort-select" value={sort} onChange={e=>{setPage(1);setSort(e.target.value)}}><option value="date">Mais recentes</option><option value="amount">Maior valor</option></select>
      <a data-testid="transactions-export-button" className="secondary" href={API+"/controls/"+control.control_id+"/transactions/export"}><Download size={16}/> Exportar CSV</a>
    </div>
    {error&&<div className="error">{error}</div>}
    <div className="transaction-table">
      <div className="table-head"><span>Descrição</span><span>Data</span><span>Tag</span><span>Valor</span><span>Ações</span></div>
      {rows.map(t=><div className="table-row" data-testid={"transaction-row-"+t.transaction_id} key={t.transaction_id}>
        <div><strong>{t.description}</strong><small>{t.note||t.user_name}</small></div>
        <span>{displayDate(t.date)}</span>
        <span>{tags.find(x=>x.tag_id===t.tag_id)?.name||"—"}</span>
        <b className={t.type}>{t.type==="income"?"+":"−"}{money(t.amount)}</b>
        {(canEdit||isOwner)&&<div className="row-actions">
          {canEdit&&<button data-testid={"edit-transaction-"+t.transaction_id} className="link-btn" onClick={()=>setEditing(t)}>Editar</button>}
          {isOwner&&<button data-testid={"delete-transaction-"+t.transaction_id} className="link-btn danger-link" onClick={()=>remove(t)}><Trash2 size={15}/></button>}
        </div>}
      </div>)}
      {!loading&&!rows.length&&<div data-testid="empty-transaction-list" className="empty">Nenhum lançamento encontrado.</div>}
      {loading&&!rows.length&&<div className="empty">Carregando lançamentos…</div>}
    </div>
    <div className="pagination">
      <button className="secondary" disabled={page<=1||loading} onClick={()=>setPage(page-1)}>Anterior</button>
      <span>Página {page} de {pageCount} · {result.total} lançamentos</span>
      <button className="secondary" disabled={page>=pageCount||loading} onClick={()=>setPage(page+1)}>Próxima</button>
    </div>
    {editing&&<EditTransactionModal control={control} tags={tags} transaction={editing} onClose={()=>setEditing(null)} onSaved={()=>{setEditing(null);load();onRefresh()}}/>}
  </section>
}
function EditTransactionModal({control,tags,transaction,onClose,onSaved}){const [form,setForm]=useState({type:transaction.type,amount:transaction.amount,date:toIsoDate(transaction.date),description:transaction.description,tag_id:transaction.tag_id,note:transaction.note||""});const save=e=>{e.preventDefault();api(`/controls/${control.control_id}/transactions/${transaction.transaction_id}`,{method:"PUT",data:form}).then(onSaved).catch(()=>alert("Confira os dados do lançamento."))};return <Modal title="Editar lançamento" onClose={onClose}><form onSubmit={save}><div className="segmented"><button type="button" data-testid="edit-type-income" className={form.type==="income"?"selected":""} onClick={()=>setForm({...form,type:"income"})}>Entrada</button><button type="button" data-testid="edit-type-expense" className={form.type==="expense"?"selected":""} onClick={()=>setForm({...form,type:"expense"})}>Saída</button></div><label>Valor<input data-testid="edit-amount-input" required min="0.01" step="0.01" type="number" value={form.amount} onChange={e=>setForm({...form,amount:e.target.value})}/></label><div className="form-grid"><label>Data<input data-testid="edit-date-input" type="date" required value={form.date} onChange={e=>setForm({...form,date:e.target.value})}/></label><label>Tag<select data-testid="edit-tag-select" required value={form.tag_id} onChange={e=>setForm({...form,tag_id:e.target.value})}>{tags.map(t=><option key={t.tag_id} value={t.tag_id}>{t.name}</option>)}</select></label></div><label>Descrição<input data-testid="edit-description-input" required value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/></label><label>Observação<input data-testid="edit-note-input" value={form.note} onChange={e=>setForm({...form,note:e.target.value})}/></label><button data-testid="edit-save-button" className="primary wide">Salvar alterações</button></form></Modal>}

function TransactionModal({control,tags,onClose,onSaved}){const [form,setForm]=useState({type:"expense",amount:"",date:today(),description:"",tag_id:tags[0]?.tag_id||"",note:""}); const save=e=>{e.preventDefault();api(`/controls/${control.control_id}/transactions`,{method:"POST",data:form}).then(onSaved).catch(()=>alert("Confira os dados do lançamento."))}; return <Modal title="Novo lançamento" onClose={onClose}><form onSubmit={save}><div className="segmented"><button type="button" data-testid="transaction-type-income" className={form.type==="income"?"selected":""} onClick={()=>setForm({...form,type:"income"})}>Entrada</button><button type="button" data-testid="transaction-type-expense" className={form.type==="expense"?"selected":""} onClick={()=>setForm({...form,type:"expense"})}>Saída</button></div><label>Valor<input data-testid="transaction-amount-input" required min="0.01" step="0.01" type="number" value={form.amount} onChange={e=>setForm({...form,amount:e.target.value})}/></label><div className="form-grid"><label>Data<input data-testid="transaction-date-input" type="date" required value={form.date} onChange={e=>setForm({...form,date:e.target.value})}/></label><label>Tag<select data-testid="transaction-tag-select" required value={form.tag_id} onChange={e=>setForm({...form,tag_id:e.target.value})}>{tags.map(t=><option key={t.tag_id} value={t.tag_id}>{t.name}</option>)}</select></label></div><label>Descrição<input data-testid="transaction-description-input" required value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/></label><label>Observação <input data-testid="transaction-note-input" value={form.note} onChange={e=>setForm({...form,note:e.target.value})}/></label><button data-testid="transaction-save-button" className="primary wide">Salvar lançamento</button></form></Modal>}
function TagsPage({control,tags,onRefresh,canEdit}){const [form,setForm]=useState({name:"",color:"#078b67",kind:"both"});const save=e=>{e.preventDefault();api(`/controls/${control.control_id}/tags`,{method:"POST",data:form}).then(()=>{setForm({...form,name:""});onRefresh()})};return <section className="panel page-panel"><div className="panel-head"><div><span className="eyebrow">Organização</span><h2>Tags do controle</h2><p className="muted">Use cores para reconhecer rapidamente cada categoria.</p></div><Tags/></div>{canEdit&&<form className="inline-form" onSubmit={save}><input data-testid="tag-name-input" required placeholder="Nome da tag" value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/><input data-testid="tag-color-input" type="color" value={form.color} onChange={e=>setForm({...form,color:e.target.value})}/><select data-testid="tag-kind-select" value={form.kind} onChange={e=>setForm({...form,kind:e.target.value})}><option value="both">Entradas e saídas</option><option value="income">Entradas</option><option value="expense">Saídas</option></select><button data-testid="tag-save-button" className="primary"><Plus size={16}/> Criar tag</button></form>}<div className="tag-grid">{tags.map(t=><div className="tag-item" key={t.tag_id}><i style={{background:t.color}}/><strong>{t.name}</strong><span>{t.kind==="both"?"Ambos":t.kind==="income"?"Entrada":"Saída"}</span></div>)}</div></section>}
function MembersPage({control,members,user,onRefresh,onDeleteControl}) {
  const [email,setEmail]=useState("");
  const [role,setRole]=useState("viewer");
  const [message,setMessage]=useState("");
  const isOwner=user.user_id===control.owner_id;
  const invite=event=>{
    event.preventDefault();
    api("/controls/"+control.control_id+"/members",{method:"POST",data:{email,role}})
      .then(()=>{setMessage("Pessoa adicionada ao controle.");setEmail("");onRefresh()})
      .catch(error=>setMessage(error.response?.data?.detail||"Não foi possível adicionar."));
  };
  const remove=async member=>{
    if(!window.confirm("Remover "+member.email+" deste controle?"))return;
    try{
      await api("/controls/"+control.control_id+"/members/"+member.user_id,{method:"DELETE"});
      setMessage("Acesso removido.");
      onRefresh();
    }catch(error){setMessage(error.response?.data?.detail||"Não foi possível remover o acesso.")}
  };
  return <section className="panel page-panel">
    <div className="panel-head"><div><span className="eyebrow">Compartilhamento</span><h2>Pessoas autorizadas</h2><p className="muted">Adicione alguém que já acessou o aplicativo.</p></div><Users/></div>
    {isOwner&&<form className="inline-form" onSubmit={invite}><input data-testid="member-email-input" type="email" required placeholder="email@exemplo.com" value={email} onChange={e=>setEmail(e.target.value)}/><select data-testid="member-role-select" value={role} onChange={e=>setRole(e.target.value)}><option value="viewer">Visualizador</option><option value="editor">Editor</option></select><button data-testid="member-invite-button" className="primary"><Plus size={16}/> Adicionar</button></form>}
    {message&&<p data-testid="member-feedback" className="muted">{message}</p>}
    <div className="member-list">{members.map(member=><div className="member-row" key={member.user_id}><div className="avatar">{member.email[0].toUpperCase()}</div><span>{member.email}</span><b>{member.role==="owner"?"Proprietário":member.role==="editor"?"Editor":"Visualizador"}</b>{isOwner&&member.role!=="owner"&&<button data-testid={"remove-member-"+member.user_id} className="icon-btn" aria-label={"Remover "+member.email} onClick={()=>remove(member)}><Trash2 size={16}/></button>}</div>)}</div>
    {isOwner&&<div className="danger-zone"><p className="muted">Excluir um controle apaga seus lançamentos, tags e insights. Antes, remova os outros membros.</p><button data-testid="delete-control-button" className="link-btn danger-link" onClick={onDeleteControl}>Excluir controle</button></div>}
  </section>;
}
function AccountSettings({user,onDeleted}) {
  const [email,setEmail]=useState("");
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  const [loadingControls,setLoadingControls]=useState(!user.is_demo);
  const [sharedControls,setSharedControls]=useState([]);
  const [transferTargets,setTransferTargets]=useState({});
  useEffect(()=>{
    if(user.is_demo)return;
    let active=true;
    const load=async()=>{
      try{
        const controls=await api("/controls");
        const owned=controls.filter(control=>control.owner_id===user.user_id);
        const details=await Promise.all(owned.map(async control=>({control,members:await api(`/controls/${control.control_id}/members`)})));
        if(active){
          const shared=details.filter(item=>item.members.some(member=>member.user_id!==user.user_id));
          setSharedControls(shared);
          setTransferTargets(current=>Object.fromEntries(shared.map(item=>[item.control.control_id,current[item.control.control_id]||""])));
        }
      }catch{if(active)setError("Não foi possível carregar os controles para preparar o encerramento.")}
      finally{if(active)setLoadingControls(false)}
    };
    load();
    return()=>{active=false};
  },[user.is_demo,user.user_id]);
  const closeAccount=async event=>{
    event.preventDefault();
    setError("");
    if(!window.confirm("Encerrar sua conta? Controles individuais serão excluídos e os compartilhados serão transferidos às pessoas escolhidas."))return;
    setLoading(true);
    try{
      const ownership_transfers=Object.fromEntries(sharedControls.map(item=>[item.control.control_id,transferTargets[item.control.control_id]]));
      await api("/auth/account",{method:"DELETE",data:{email,ownership_transfers}});
      onDeleted();
    }catch(reason){
      setError(reason.response?.data?.detail||"Não foi possível encerrar a conta.");
    }finally{setLoading(false)}
  };
  return <section className="panel page-panel account-settings">
    <div className="panel-head"><div><span className="eyebrow">Privacidade e dados</span><h2>Encerrar conta</h2><p className="muted">Conta conectada: {user.email}</p></div><Settings2/></div>
    {user.is_demo?<div className="account-note">A conta de demonstração e seus dados temporários são removidos quando você sai.</div>:<>
      <div className="account-note"><strong>O que será removido:</strong> seu perfil local, sessões e dados de controles individuais que você possui. Para cada controle compartilhado de sua propriedade, escolha quem assumirá a propriedade; o controle e seu histórico financeiro serão preservados. Nos controles de outras pessoas, seu acesso será removido e a autoria dos seus lançamentos será anonimizada. Seu login Google é gerido pelo provedor de autenticação e não é apagado; se entrar novamente, um novo perfil local será criado.</div>
      {loadingControls&&<p className="muted">Carregando controles compartilhados…</p>}
      <form className="account-confirm-form" onSubmit={closeAccount}>
      {sharedControls.map(({control,members})=><label className="owner-transfer-field" key={control.control_id}>Novo proprietário de “{control.name}”<select data-testid={`account-transfer-${control.control_id}`} required value={transferTargets[control.control_id]||""} onChange={event=>setTransferTargets(current=>({...current,[control.control_id]:event.target.value}))}><option value="">Selecione uma pessoa</option>{members.filter(member=>member.user_id!==user.user_id).map(member=><option key={member.user_id} value={member.user_id}>{member.email||member.user_id}</option>)}</select></label>)}
        <label>Digite seu e-mail para confirmar<input data-testid="delete-account-email" type="email" required autoComplete="email" value={email} onChange={event=>setEmail(event.target.value)}/></label>
        <button data-testid="delete-account-button" className="danger-button" disabled={loading||loadingControls}>{loading?"Encerrando…":"Excluir conta e dados"}</button>
      </form>
      {error&&<div data-testid="delete-account-error" className="error">{error}</div>}
    </>}
  </section>;
}
function Page({user,onLogout,onAccountDeleted}){
  const nav=useNavigate();
  const [controls,setControls]=useState([]),[control,setControl]=useState(null),[tags,setTags]=useState([]),[members,setMembers]=useState([]),[transactions,setTransactions]=useState([]);
  const refresh=useCallback(()=>control&&Promise.all([api(`/controls/${control.control_id}/tags`),api(`/controls/${control.control_id}/members`),api(`/controls/${control.control_id}/transactions?page=1&page_size=20`)]).then(([a,b,c])=>{setTags(a);setMembers(b);setTransactions(c.items)}),[control]);
  useEffect(()=>{api("/controls").then(items=>{setControls(items);setControl(items[0]||null)})},[]);
  useEffect(()=>{if(control)refresh()},[control,refresh]);
  const currentRole=members.find(member=>member.user_id===user.user_id)?.role;
  const canEdit=currentRole==="owner"||currentRole==="editor";
  const isOwner=currentRole==="owner";
  const path=window.location.pathname;
  const shellProps={user,onLogout,control,setControl,controls,onAccount:()=>nav("/conta")};
  if(path==="/conta")return <Shell {...shellProps}><AccountSettings user={user} onDeleted={onAccountDeleted}/></Shell>;
  if(!control)return <Shell {...shellProps}><div className="empty-page"><WalletCards size={40}/><h2>Comece seu controle financeiro</h2><p>Crie seu primeiro controle para acompanhar entradas, saídas e objetivos.</p><button data-testid="create-control-button" className="primary" onClick={async()=>{const name=prompt("Nome do controle");if(name){const created=await api("/controls",{method:"POST",data:{name,description:""}});setControls([created]);setControl(created)}}}><Plus/> Criar controle</button></div></Shell>;
  let view=<Dashboard {...{control,tags,members,transactions,onRefresh:refresh,canEdit,isOwner}}/>;
  if(path==="/lancamentos")view=<TransactionsPage control={control} tags={tags} transactions={transactions} onRefresh={refresh} user={user} members={members}/>;
  if(path==="/tags")view=<TagsPage control={control} tags={tags} onRefresh={refresh} canEdit={canEdit}/>;
  if(path==="/membros")view=<MembersPage control={control} members={members} user={user} onRefresh={refresh} onDeleteControl={async()=>{if(!window.confirm("Excluir este controle e todos os seus dados?"))return;try{await api("/controls/"+control.control_id,{method:"DELETE"});const next=await api("/controls");setControls(next);setControl(next[0]||null)}catch(error){alert(error.response?.data?.detail||"Não foi possível excluir o controle.")}}}/>;
  return <Shell {...shellProps}>{view}<AiInsights key={control.control_id} control={control}/></Shell>;
}
function AppRouter(){const [user,setUser]=useState(null),[authConfig,setAuthConfig]=useState({google_enabled:false,demo_enabled:false}),[loading,setLoading]=useState(true); useEffect(()=>{Promise.all([api("/auth/config").catch(()=>({google_enabled:false,demo_enabled:false})),api("/auth/me").catch(()=>null)]).then(([config,currentUser])=>{setAuthConfig(config);setUser(currentUser)}).finally(()=>setLoading(false))},[]); if(loading)return <main className="auth-page"><div className="loader"/></main>; if(!user)return <Login onLogin={setUser} authConfig={authConfig}/>; return <Page user={user} onLogout={()=>api("/auth/logout",{method:"POST"}).then(()=>setUser(null))} onAccountDeleted={()=>setUser(null)}/>}
function AiInsights({control}){
  const [text,setText]=useState(""),[loading,setLoading]=useState(false),[error,setError]=useState("");
  const generate=async()=>{
    setLoading(true);setText("");setError("");
    try{
      const response=await fetch(`${API}/controls/${control.control_id}/ai/insights`,{method:"POST",credentials:"include"});
      if(!response.ok){let detail="";try{detail=(await response.json()).detail||""}catch{}throw new Error(detail||"Não foi possível gerar os insights agora.")}
      const reader=response.body.getReader(),decoder=new TextDecoder();let buffer="";
      while(true){const {value,done}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});const parts=buffer.split("\n\n");buffer=parts.pop();for(const line of parts){const raw=line.replace(/^data:\s*/,"");if(!raw)continue;const event=JSON.parse(raw);if(event.text)setText(prev=>prev+event.text);if(event.error)setError(event.error)}}
    }catch(error){setError(error.message||"Não foi possível gerar os insights agora.")}
    finally{setLoading(false)}
  };
  return <section className="ai-panel"><div className="ai-heading"><div><span className="eyebrow">Assistente financeiro</span><h3>Insights com Gemini</h3><p className="muted">Análise baseada apenas nos seus totais agregados. Novas análises têm intervalo de até 10 minutos; resultados em cache podem ser consultados novamente.</p></div><button data-testid="generate-ai-insights-button" className="primary" onClick={generate} disabled={loading}>{loading?"Analisando…":"Gerar insights"}</button></div>{text&&<p data-testid="ai-insights-result" className="ai-result">{text}</p>}{error&&<div data-testid="ai-insights-error" className="error">{error}</div>}</section>;
}
export default function App(){return <BrowserRouter><AppRouter/></BrowserRouter>}
