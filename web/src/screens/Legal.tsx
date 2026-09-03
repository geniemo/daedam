import type { ReactNode } from 'react'

/**
 * 이용약관·개인정보처리방침.
 *
 * 로그인 전에도 읽혀야 해서 공개 라우트다(온보딩·랜딩이 링크한다). 내용은
 * **실제 동작만 적는다** — 안 하는 것을 한다고 적으면 문서가 거짓말이 되고,
 * 하는 것을 빼면 동의가 무효가 된다. 특히 음성·영상·얼굴 스틸의 Gemini 처리와
 * 탈퇴 시 전체 삭제는 코드로 구현된 사실 그대로다(accounts.delete cascade +
 * InterviewStore.delete_user_files).
 */

const EFFECTIVE = '2026년 9월 3일'

function LegalPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="mx-auto max-w-[720px] px-8 pt-[52px] pb-24 animate-dm-fade">
      <a href="/" className="text-[13px] text-faint hover:text-muted">
        ← 대담으로 돌아가기
      </a>
      <h1 className="mt-[22px] mb-0 text-[26px] font-bold tracking-[-.03em] text-ink">{title}</h1>
      <p className="mt-[8px] mb-0 text-[12.5px] text-faint">시행일: {EFFECTIVE}</p>
      <div className="mt-[28px] flex flex-col gap-[26px]">{children}</div>
    </main>
  )
}

function Section({ heading, children }: { heading: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-[10px]">
      <h2 className="m-0 text-[15.5px] font-bold text-ink">{heading}</h2>
      <div className="flex flex-col gap-[8px] text-[13.5px] leading-[1.75] text-body-2">
        {children}
      </div>
    </section>
  )
}

function Items({ items }: { items: string[] }) {
  return (
    <ul className="m-0 flex list-none flex-col gap-[6px] p-0">
      {items.map((item) => (
        <li key={item} className="flex gap-[8px]">
          <span className="text-accent">·</span>
          <span>{item}</span>
        </li>
      ))}
    </ul>
  )
}

export function Terms() {
  return (
    <LegalPage title="이용약관">
      <Section heading="제1조 (목적)">
        <p className="m-0">
          이 약관은 대담(이하 "서비스")의 이용 조건과 이용자·운영자의 권리와 의무를
          정합니다. 서비스는 AI가 진행하는 음성 모의면접과 그 결과 리포트를
          제공합니다.
        </p>
      </Section>
      <Section heading="제2조 (계정)">
        <p className="m-0">
          서비스는 카카오·구글 계정으로 가입합니다. 이용자는 본인의 계정으로만
          이용해야 하며, 계정 관리 책임은 이용자에게 있습니다.
        </p>
      </Section>
      <Section heading="제3조 (서비스의 내용)">
        <Items
          items={[
            '등록한 회사·직무의 공개 자료를 조사해 면접 질문을 만듭니다.',
            'AI 면접관과 음성으로 모의면접을 진행합니다.',
            '면접이 끝나면 답변 내용·말하기·시선·표정에 대한 리포트를 만듭니다.',
          ]}
        />
        <p className="m-0">
          질문·평가·코칭은 AI가 생성하며 사실과 다르거나 부정확할 수 있습니다.
          서비스는 연습 도구이고, 실제 채용의 과정·결과와 무관하며 이를 보증하지
          않습니다.
        </p>
      </Section>
      <Section heading="제4조 (크레딧)">
        <p className="m-0">
          면접 등 일부 기능은 크레딧을 차감합니다. 크레딧은 현재 가입·쿠폰으로
          무상 지급되며, 유상 판매를 시작할 때는 별도로 고지합니다. 무상 크레딧은
          환불 대상이 아닙니다.
        </p>
      </Section>
      <Section heading="제5조 (이용자의 콘텐츠)">
        <p className="m-0">
          이용자가 입력한 지원서 등 콘텐츠의 권리는 이용자에게 있습니다. 이용자는
          서비스 제공(질문 생성·면접 진행·리포트 작성)에 필요한 범위에서 서비스가
          이를 처리하는 것을 허락합니다.
        </p>
      </Section>
      <Section heading="제6조 (금지 행위)">
        <Items
          items={[
            '타인의 정보로 가입하거나 타인의 계정을 쓰는 행위',
            '서비스의 정상적 운영을 방해하는 행위',
            '법령이나 공서양속에 어긋나는 목적의 이용',
          ]}
        />
      </Section>
      <Section heading="제7조 (책임의 한계)">
        <p className="m-0">
          운영자는 무료로 제공되는 기능에 대해 법령이 허용하는 범위에서 책임을
          제한합니다. AI 출력의 정확성·완전성은 보증되지 않습니다.
        </p>
      </Section>
      <Section heading="제8조 (약관의 변경과 서비스 중단)">
        <p className="m-0">
          약관을 바꾸면 시행 전에 서비스 안에서 알립니다. 서비스는 사전 고지 후
          변경되거나 중단될 수 있습니다. 이 약관은 대한민국 법에 따릅니다.
        </p>
      </Section>
    </LegalPage>
  )
}

export function Privacy() {
  return (
    <LegalPage title="개인정보처리방침">
      <Section heading="1. 수집하는 정보">
        <Items
          items={[
            '계정: 로그인 제공자(카카오·구글)의 이용자 식별자, 이름, 이메일, 프로필 사진',
            '이용자 입력: 온보딩에서 입력한 이름, 지원 회사·직무, 지원서 내용',
            '면접 기록: 음성 녹음과 전사, 웹캠 영상, 3초 간격의 스틸 이미지, 시선·표정 측정값',
            '이용 기록: 크레딧 사용·지급 내역',
          ]}
        />
      </Section>
      <Section heading="2. 이용 목적">
        <Items
          items={[
            '면접 질문 생성과 실시간 음성 면접 진행',
            '리포트 작성 — 답변 평가, 말하기·시선·표정 분석과 코칭',
            '계정 식별과 크레딧 관리',
          ]}
        />
      </Section>
      <Section heading="3. 처리 위탁과 국외 이전">
        <p className="m-0">
          면접과 분석은 Google의 Gemini API(미국 등 국외 소재 서버)로 처리됩니다.
          이전되는 항목은 면접 음성(실시간), 전사·지원서 텍스트, 웹캠 스틸
          이미지이며, 목적은 실시간 면접 대화와 리포트 분석입니다. 처리된 데이터는
          Google의 API 데이터 정책을 따릅니다.
        </p>
      </Section>
      <Section heading="4. 보관과 파기">
        <p className="m-0">
          면접 기록은 이용자가 리포트를 다시 볼 수 있도록 서비스 이용 기간 동안
          보관합니다. 탈퇴하면 계정·준비 자료·면접 기록(녹음·영상·스틸 포함)·크레딧
          내역이 즉시 삭제됩니다.
        </p>
      </Section>
      <Section heading="5. 이용자의 권리">
        <Items
          items={[
            '내 정보 화면에서 계정 정보를 확인할 수 있습니다.',
            '탈퇴로 언제든 동의를 철회하고 모든 데이터를 삭제할 수 있습니다.',
          ]}
        />
      </Section>
      <Section heading="6. 문의">
        <p className="m-0">
          개인정보 처리에 관한 문의는 [운영자 연락처]로 보내 주세요.
        </p>
      </Section>
    </LegalPage>
  )
}
